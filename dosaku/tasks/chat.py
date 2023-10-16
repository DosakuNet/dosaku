from abc import abstractmethod
from typing import Generator, Union

from dosaku import Task


class Chat(Task):
    """Interface for a generic conversational chatbot."""
    name = 'Chat'

    def __init__(self):
        super().__init__()

    @abstractmethod
    def message(self, message: str, **kwargs) -> Union[str, Generator[str, None, None]]:
        """Send a message to the agent and get a response.

        It is up to the chat module whether a chat history is kept and used. It is also up to the module whether
        streaming is supported.

        Args:
            message: The message to send the chat agent.

        Returns:
            An AI chat response. The response may be in one of two forms:

                - non-streaming: The expected default behavior, if a module is in non-streaming mode it should return
                    the response as a string directly;
                - streaming: If the module supports and is set to streaming, it should return a generator object that
                    yields an updated string response every iteration;

        Non-streaming Example::

            from dosaku import Agent

            agent = Agent()
            agent.learn('Chat', module='EchoBot')
            response = agent.Chat.message('Hello!')  # Hi, I'm EchoBot. You said: "Hello!".

        Streaming Example::

            from dosaku import Agent

            agent = Agent()
            agent.learn('Chat', module='EchoBot', stream=True)
            for partial_response in agent.Chat.message('Hello!):
                print(partial_response)

            # H
            # Hi
            # Hi,
            # ...
            # Hi, I'm EchoBot. You said: "Hello
            # Hi, I'm EchoBot. You said: "Hello!
            # Hi, I'm EchoBot. You said: "Hello!"

        OpenAI GPT Streaming in a Gradio App Example (Requires the OpenAI service)::

            import gradio as gr
            from dosaku import Agent, Config

            agent = Agent(enable_services=True)
            agent.learn('Chat', module='OpenAIChat', model=Config()['OPENAI']['DEFAULT_MODEL'], stream=True)

            def predict(message, _):
                for partial_response in agent.Chat(message):  # __call__() defaults to message()
                    yield partial_response

            gr.ChatInterface(predict).queue().launch()

        """

    @abstractmethod
    def __call__(self, *args, **kwargs):
        return self.message(*args, **kwargs)


Chat.register_task()
