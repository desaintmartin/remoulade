import logging
import os
import random
import subprocess
import sys

import pylibmc
import pytest
import redis

import remoulade
from remoulade import Worker
from remoulade.brokers.local import LocalBroker
from remoulade.brokers.rabbitmq import RabbitmqBroker
from remoulade.brokers.stub import StubBroker
from remoulade.rate_limits import backends as rl_backends
from remoulade.results import backends as res_backends

logfmt = "[%(asctime)s] [%(threadName)s] [%(name)s] [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=logfmt)
logging.getLogger("pika").setLevel(logging.WARN)

random.seed(1337)

CI = os.getenv("TRAVIS") == "true" or \
    os.getenv("APPVEYOR") == "true"


def check_rabbitmq(broker):
    try:
        broker.connection
    except Exception as e:
        raise e if CI else pytest.skip("No connection to RabbmitMQ server.")


def check_redis(client):
    try:
        client.ping()
    except redis.ConnectionError as e:
        raise e if CI else pytest.skip("No connection to Redis server.")


@pytest.fixture()
def stub_broker():
    broker = StubBroker()
    broker.emit_after("process_boot")
    remoulade.set_broker(broker)
    yield broker
    broker.flush_all()
    broker.close()


@pytest.fixture()
def rabbitmq_broker():
    broker = RabbitmqBroker(host="127.0.0.1")
    check_rabbitmq(broker)
    broker.emit_after("process_boot")
    remoulade.set_broker(broker)
    yield broker
    broker.flush_all()
    broker.close()


@pytest.fixture()
def local_broker():
    broker = LocalBroker()
    broker.emit_after("process_boot")
    remoulade.set_broker(broker)
    yield broker
    broker.flush_all()
    broker.close()


@pytest.fixture()
def stub_worker(stub_broker):
    worker = Worker(stub_broker, worker_timeout=100, worker_threads=32)
    worker.start()
    yield worker
    worker.stop()


@pytest.fixture()
def rabbitmq_worker(rabbitmq_broker):
    worker = Worker(rabbitmq_broker, worker_threads=32)
    worker.start()
    yield worker
    worker.stop()


@pytest.fixture()
def redis_worker(redis_broker):
    worker = Worker(redis_broker, worker_threads=32)
    worker.start()
    yield worker
    worker.stop()


@pytest.fixture
def info_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    yield
    logger.setLevel(logging.DEBUG)


@pytest.fixture
def start_cli():
    proc = None

    def run(broker_module, *, extra_args=None, **kwargs):
        nonlocal proc
        args = [sys.executable, "-m", "remoulade", broker_module]
        proc = subprocess.Popen(args + (extra_args or []), **kwargs)
        return proc

    yield run

    if proc is not None:
        proc.terminate()
        proc.wait()


@pytest.fixture
def redis_rate_limiter_backend():
    backend = rl_backends.RedisBackend()
    check_redis(backend.client)
    backend.client.flushall()
    return backend


@pytest.fixture
def stub_rate_limiter_backend():
    return rl_backends.StubBackend()


@pytest.fixture
def rate_limiter_backends(redis_rate_limiter_backend, stub_rate_limiter_backend):
    return {
        "redis": redis_rate_limiter_backend,
        "stub": stub_rate_limiter_backend,
    }


@pytest.fixture
def redis_result_backend():
    backend = res_backends.RedisBackend()
    check_redis(backend.client)
    backend.client.flushall()
    return backend


@pytest.fixture
def stub_result_backend():
    return res_backends.StubBackend()


@pytest.fixture
def result_backends(redis_result_backend, stub_result_backend):
    return {
        "redis": redis_result_backend,
        "stub": stub_result_backend,
    }
