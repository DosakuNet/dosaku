from __future__ import annotations
from typing import Dict, List, Optional, TYPE_CHECKING, Union

from dosaku import (Config, module_manager, ShortTermModule, Task, task_hub,
                    ServicePermissionRequired, ExecutorPermissionRequired, ModuleForTaskNotFound)
from dosaku.core.actor import Actor
from dosaku.utils import ifnone
from dosaku import tasks  # Do not remove: allows all tasks in the dosaku.tasks namespace to register themselves
from dosaku import modules  # Do not remove: allows all modules in the dosaku.modules namespace to register themselves
if TYPE_CHECKING:
    from dosaku.tasks import Chat
    from dosaku.logic import Context


class Agent:
    config = Config()
    task_hub = task_hub
    module_manager = module_manager

    def __init__(self, name: str = 'Agent', enable_services: bool = False, enable_executors: bool = False):
        self.name = name
        self._known_tasks: Dict[str: List[str]] = dict()
        self._memorized_tasks: Dict[str: List[str]] = dict()
        self._allow_services = enable_services
        self._allow_executors = enable_executors
        self.subagents: Dict[str, Agent] = dict()

    @classmethod
    def register_task(cls, task: Task):
        cls.task_hub.register_task(task)

    def spawn_subagent(self, name, enable_services: Optional[bool] = None, enable_executors: Optional[bool] = None):
        enable_services = ifnone(enable_services, default=self.services_enabled)
        enable_executors = ifnone(enable_executors, default=self.executors_enabled)
        if name in self.subagents.keys():
            raise ValueError(f'Sub agent {name} already exists.')
        self.subagents[name] = Agent(name=name, enable_services=enable_services, enable_executors=enable_executors)

    def remove_subagent(self, name):
        del self.subagents[name]

    def api(self, task: str):
        """Returns the actions for the given task."""
        if task in self.task_hub.tasks:
            return self.task_hub.api(task)
        elif task in self.memorized_tasks:
            return self._memorized_tasks[task]

    def doc(self, task: str, action: Optional[str] = None):
        """Returns documentation on the given task action."""
        return self.task_hub.doc(task=task, action=action)

    @property
    def learnable_tasks(self):
        """Returns a list of all learnable tasks."""
        return list(self.task_hub.tasks.keys())

    @property
    def tasks(self):
        """Returns a list of all known tasks, both learned and memorized."""
        return self.known_tasks + self.memorized_tasks

    @property
    def known_tasks(self):
        return list(self._known_tasks.keys())

    @property
    def memorized_tasks(self):
        return list(self._memorized_tasks)

    def registered_modules(self, task: str):
        return self.task_hub.registered_modules(task)

    def loaded_modules(self):
        return self.module_manager.modules

    def enable_services(self):
        self._allow_services = True

    def disable_services(self):
        self._allow_services = False

    @property
    def services_enabled(self):
        return self._allow_services

    def _assert_services_enabled(self):
        if not self.services_enabled:
            raise ServicePermissionRequired(
                f'{self.__class__} requires services be enabled. Pass in enable_services=True on init.')

    def enable_executors(self):
        self._allow_executors = True

    def disable_executors(self):
        self._allow_executors = False

    @property
    def executors_enabled(self):
        return self._allow_executors

    def _assert_executors_enabled(self):
        if not self.executors_enabled:
            raise ExecutorPermissionRequired(
                f'{self.__class__} requires executors to be enabled. Pass in enable_executors=True on init.')

    def learn(self, task: Union[str, Task], module: Optional[str] = None, force_relearn=False, **kwargs):
        """Learn a task via a pre-existing module."""
        if isinstance(task, Task):
            task = task.name

        if module is None:
            modules = self.task_hub.registered_modules(task)
            if modules is None:
                raise ModuleForTaskNotFound(f'There are no known modules which have registered the task {task}.')
            module = modules[0]

        print(f'Attemping to learn {task} via the module {module}.')
        try:
            self.module_manager.load_module(
                module,
                force_reload=force_relearn,
                allow_services=self.services_enabled,
                allow_executors=self.executors_enabled,
                **kwargs)
        except RuntimeError as err:
            raise err

        # We need to create a new Actor class here to be able to define new class methods, e.g. __call__. If we don't
        # create new class, every module that overwrites class methods will be overwriting each other.
        class _Actor(Actor):
            def __init__(self):
                super().__init__()

        setattr(self, task, _Actor())
        for method in self.task_hub.api(task):
            module_attr = self.module_manager.get_module_attr(module, method)
            if '__' in module_attr.__name__:
                actor_class = type(getattr(self, task))
                setattr(actor_class, method, module_attr)
            else:
                actor_object = getattr(self, task)
                setattr(actor_object, method, module_attr)
        self._known_tasks[task] = self.task_hub.api(task)

    def memorize(self, stm: ShortTermModule, actions: Optional[Union[str, List[str]]] = None):
        """Equivalent to learn, but for dynamically generated code made available through a ShortTermModule."""
        setattr(self, stm.name, stm)
        if actions is None:
            actions = list(stm.api().keys())
        elif isinstance(actions, str):
            actions = list(actions)
        self._memorized_tasks[stm.name] = actions

    def memorize_from_context(self, context: Context) -> Context:
        """Memorizes a ShortTermModule from the given context.

        The context must have stored the ShortTermModule in its short_term_memory attribute.
        """
        from dosaku.tasks import Chat  # avoid circular import
        self.memorize(context.short_term_memory)
        message = Chat.Message(
            sender='assistant',
            message=f'Memorized the ShortTermModule {context.short_term_memory.name} from the context\'s short term '
                    f'memory.')
        context.conversation.add_message(message)
        return context
