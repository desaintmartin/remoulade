# This file is a part of Remoulade.
#
# Copyright (C) 2017,2018 CLEARTYPE SRL <bogdan@cleartype.io>
#
# Remoulade is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# Remoulade is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public
# License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


class MiddlewareError(Exception):
    """Base class for middleware errors."""


class SkipMessage(MiddlewareError):
    """An exception that may be raised by Middleware inside the
    ``before_process_message`` hook in order to skip a message.
    """


class Middleware:
    """Base class for broker middleware.  The default implementations
    for all hooks are no-ops and subclasses may implement whatever
    subset of hooks they like.
    """

    def get_option(self, option_name, *, broker, message, default=None):

        # get option at message level
        option = message.options.get(option_name)
        if option is not None:
            return option

        # it doesn't make sense to get pipe_target and group_info at any other level than message
        if option == "pipe_target" or option == "group_info":
            return None

        # get option at actor level
        actor = broker.get_actor(message.actor_name)
        option = actor.options.get(option_name)
        if option is not None:
            return option

        # get option at middleware level or return default value
        return getattr(self, option_name, default)

    @property
    def actor_options(self):
        """The set of options that may be configured on each actor."""
        return set()

    def before_ack(self, broker, message):
        """Called before a message is acknowledged."""

    def after_ack(self, broker, message):
        """Called after a message has been acknowledged."""

    def before_nack(self, broker, message):
        """Called before a message is rejected."""

    def after_nack(self, broker, message):
        """Called after a message has been rejected."""

    def before_declare_actor(self, broker, actor):
        """Called before an actor is declared."""

    def after_declare_actor(self, broker, actor):
        """Called after an actor has been declared."""

    def before_declare_queue(self, broker, queue_name):
        """Called before a queue is declared."""

    def after_declare_queue(self, broker, queue_name):
        """Called after a queue has been declared."""

    def after_declare_delay_queue(self, broker, queue_name):
        """Called after a delay queue has been declared."""

    def before_enqueue(self, broker, message, delay):
        """Called before a message is enqueued."""

    def after_enqueue(self, broker, message, delay):
        """Called after a message has been enqueued."""

    def before_delay_message(self, broker, message):
        """Called before a message has been delayed in worker memory."""

    def before_process_message(self, broker, message):
        """Called before a message is processed.

        Raises:
          SkipMessage: If the current message should be skipped.  When
            this is raised, ``after_skip_message`` is emitted instead
            of ``after_process_message``.
        """

    def after_process_message(self, broker, message, *, result=None, exception=None):
        """Called after a message has been processed."""

    def after_worker_thread_process_message(self, broker, thread):
        """Called after a worker thread has finished processing a message"""

    def after_skip_message(self, broker, message):
        """Called instead of ``after_process_message`` after a message
        has been skippped.
        """

    def after_message_canceled(self, broker, message):
        """Called instead of ``after_process_message`` after a message
        has been canceled.
        """

    def after_process_boot(self, broker):
        """Called immediately after subprocess start up."""

    def before_process_stop(self, broker):
        """Called before after subprocess stop."""

    def before_worker_boot(self, broker, worker):
        """Called before the worker process starts up."""

    def after_worker_boot(self, broker, worker):
        """Called after the worker process has started up."""

    def before_worker_shutdown(self, broker, worker):
        """Called before the worker process shuts down."""

    def after_worker_shutdown(self, broker, worker):
        """Called after the worker process shuts down."""

    def before_consumer_thread_shutdown(self, broker, thread):
        """Called before a consumer thread shuts down.  This may be
        used to clean up thread-local resources (such as Django
        database connections).

        There is no ``after_consumer_thread_boot``.
        """

    def before_worker_thread_shutdown(self, broker, thread):
        """Called before a worker thread shuts down.  This may be used
        to clean up thread-local resources (such as Django database
        connections).

        There is no ``after_worker_thread_boot``.
        """

    def after_enqueue_pipe_target(self, broker, group_info):
        """Called after the pipe target of a message has been enqueued"""

    def before_build_group_pipeline(self, broker, group_id, message_ids):
        """Called before a group in a group pipeline is enqueued"""

    def update_options_before_create_message(self, options, broker, actor_name):
        """Called when a message is being built.
        The message options is set to this function's return value"""

        return options
