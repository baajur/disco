import inspect
import functools

from disco.util.logging import LoggingClass
from disco.bot.command import Command, CommandError


class PluginDeco(object):
    @staticmethod
    def add_meta_deco(meta):
        def deco(f):
            if not hasattr(f, 'meta'):
                f.meta = []

            f.meta.append(meta)

            return f
        return deco

    @classmethod
    def listen(cls, event_name):
        return cls.add_meta_deco({
            'type': 'listener',
            'event_name': event_name,
        })

    @classmethod
    def command(cls, *args, **kwargs):
        return cls.add_meta_deco({
            'type': 'command',
            'args': args,
            'kwargs': kwargs,
        })

    @classmethod
    def pre_command(cls):
        return cls.add_meta_deco({
            'type': 'pre_command',
        })

    @classmethod
    def post_command(cls):
        return cls.add_meta_deco({
            'type': 'post_command',
        })

    @classmethod
    def pre_listener(cls):
        return cls.add_meta_deco({
            'type': 'pre_listener',
        })

    @classmethod
    def post_listener(cls):
        return cls.add_meta_deco({
            'type': 'post_listener',
        })


class Plugin(LoggingClass, PluginDeco):
    def __init__(self, bot, config):
        super(Plugin, self).__init__()
        self.bot = bot
        self.client = bot.client
        self.state = bot.client.state
        self.config = config

        self.listeners = []
        self.commands = {}

        self._pre = {'command': [], 'listener': []}
        self._post = {'command': [], 'listener': []}

        for name, member in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(member, 'meta'):
                for meta in member.meta:
                    if meta['type'] == 'listener':
                        self.register_listener(member, meta['event_name'])
                    elif meta['type'] == 'command':
                        self.register_command(member, *meta['args'], **meta['kwargs'])
                    elif meta['type'].startswith('pre_') or meta['type'].startswith('post_'):
                        when, typ = meta['type'].split('_', 1)
                        self.register_trigger(typ, when, member)

    def execute(self, event):
        try:
            return event.command.execute(event)
        except CommandError as e:
            event.msg.reply(e.message)
            return False

    def register_trigger(self, typ, when, func):
        getattr(self, '_' + when)[typ].append(func)

    def _dispatch(self, typ, func, event, *args, **kwargs):
        for pre in self._pre[typ]:
            event = pre(event, args, kwargs)

        if event is None:
            return False

        result = func(event, *args, **kwargs)

        for post in self._post[typ]:
            post(event, args, kwargs, result)

        return True

    def register_listener(self, func, name):
        func = functools.partial(self._dispatch, 'listener', func)
        self.listeners.append(self.bot.client.events.on(name, func))

    def register_command(self, func, *args, **kwargs):
        wrapped = functools.partial(self._dispatch, 'command', func)
        self.commands[func.__name__] = Command(self, wrapped, *args, **kwargs)

    def destroy(self):
        map(lambda k: k.remove(), self._events)

    def load(self):
        pass

    def unload(self):
        pass