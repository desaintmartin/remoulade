""" This file describe the API to get the state of messages """
import datetime
import sys
from collections import defaultdict
from typing import Dict, Iterable, List

from flask import Flask, request
from marshmallow import ValidationError
from typing_extensions import DefaultDict, TypedDict
from werkzeug.exceptions import HTTPException, NotFound

from remoulade import get_broker, get_scheduler
from remoulade.errors import NoResultBackend, NoScheduler, RemouladeError
from remoulade.result import Result
from remoulade.results import ResultMissing

from ..state.backends import PostgresBackend
from .schema import DeleteSchema, MessageSchema, PageSchema

app = Flask(__name__)


def dict_has(item, keys, value):
    """Check if the value of some key in keys has a value"""
    return chr(0).join([str(item[k]) for k in keys if item.get(k)]).lower().find(value) >= 0


class GroupMessagesT(TypedDict):
    group_id: str
    messages: List[dict]


@app.route("/messages/states", methods=["POST"])
def get_states():
    states_kwargs = PageSchema().load(request.json or {})
    backend = get_broker().get_state_backend()
    data = [state.as_dict() for state in backend.get_states(**states_kwargs)]
    return {"data": data, "count": len(data)}


@app.route("/messages/states", methods=["DELETE"])
def clean_states():
    backend = get_broker().get_state_backend()
    if not isinstance(backend, PostgresBackend):
        return {"error": "deleting states is only supported by the PostgresBackend"}, 400
    states_kwargs = DeleteSchema().load(request.json or {})
    get_broker().get_state_backend().clean(**states_kwargs)
    return {"result": "ok"}


@app.route("/messages/state/<message_id>")
def get_state(message_id):
    backend = get_broker().get_state_backend()
    data = backend.get_state(message_id)
    if data is None:
        raise NotFound("message_id = {} does not exist".format(message_id))
    return data.as_dict(encode_args=True)


@app.route("/messages/cancel/<message_id>", methods=["POST"])
def cancel_message(message_id):
    backend = get_broker().get_cancel_backend()
    backend.cancel([message_id])
    return {"result": "ok"}


@app.route("/messages/requeue/<message_id>")
def requeue_message(message_id):
    broker = get_broker()
    backend = broker.get_state_backend()
    state = backend.get_state(message_id)
    actor = broker.get_actor(state.actor_name)
    payload = {"args": state.args, "kwargs": state.kwargs}
    pipe_target = state.options.get("pipe_target")
    if pipe_target is None:
        actor.send_with_options(**payload, **state.options)
        return {"result": "ok"}
    else:
        return {"error": "requeue message in a pipeline not supported"}, 400


@app.route("/messages/result/<message_id>")
def get_results(message_id):
    from ..message import get_encoder

    max_size = 1e4
    try:
        result = Result(message_id=message_id).get()
        encoded_result = get_encoder().encode(result).decode("utf-8")
        size_result = sys.getsizeof(encoded_result)
        if size_result >= max_size:
            encoded_result = "The result is too big {}M".format(size_result / 1e6)
        return {"result": encoded_result}
    except ResultMissing:
        return {"result": "result is missing"}
    except NoResultBackend:
        return {"result": "no result backend"}
    except (UnicodeDecodeError, TypeError):
        return {"result": "non serializable result"}


@app.route("/scheduled/jobs")
def get_scheduled_jobs():
    try:
        scheduler = get_scheduler()
    except NoScheduler:
        return {"result": []}
    scheduled_jobs = scheduler.get_redis_schedule()
    return {"result": [job.as_dict() for job in scheduled_jobs.values()]}


@app.route("/messages", methods=["POST"])
def enqueue_message():
    payload = MessageSchema().load(request.json)
    actor = get_broker().get_actor(payload.pop("actor_name"))
    options = payload.pop("options") or {}
    actor.send_with_options(**payload, **options)
    return {"result": "ok"}


@app.route("/actors")
def get_actors():
    return {"result": [actor.as_dict() for actor in get_broker().actors.values()]}


@app.route("/groups", methods=["POST"])
def get_groups():
    backend = get_broker().get_state_backend()
    groups_by_id: DefaultDict[str, List[Dict]] = defaultdict(list)
    states = (state for state in backend.get_states(get_groups=True))

    for state in states:
        groups_by_id[state.group_id].append(state.as_dict(exclude_keys=("args", "kwargs", "options")))

    groups: Iterable[GroupMessagesT] = (
        {"group_id": group_id, "messages": messages} for group_id, messages in groups_by_id.items()
    )
    sorted_groups: List[GroupMessagesT] = sorted(
        groups, key=lambda x: x["messages"][0].get("enqueued_datetime") or datetime.datetime.min, reverse=True
    )
    if request.json is None:
        return {"data": sorted_groups, "count": len(sorted_groups)}

    states_kwargs = PageSchema().load(request.json)
    return {
        "data": sorted_groups[states_kwargs["offset"] : states_kwargs["size"] + states_kwargs["offset"]],
        "count": len(sorted_groups),
    }


@app.route("/options")
def get_options():
    broker = get_broker()
    return {"options": list(broker.actor_options)}


@app.errorhandler(RemouladeError)
def remoulade_exception(e):
    return {"error": str(e)}, 500


@app.errorhandler(HTTPException)
def http_exception(e):
    return {"error": str(e)}, e.code


@app.errorhandler(ValidationError)
def validation_error(e):
    return {"error": e.normalized_messages()}, 400
