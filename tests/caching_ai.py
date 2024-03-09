import json
import os.path

from pathlib import Path
from typing import List, Optional, Union

from langchain.schema import AIMessage, HumanMessage, SystemMessage

from gpt_engineer.core.ai import AI
from gpt_engineer.core.token_usage import TokenUsageLog
from gpt_engineer.core.prompt import Prompt

# Type hint for a chat message
Message = Union[AIMessage, HumanMessage, SystemMessage]


class CachingAI(AI):
    def __init__(self, *args, **kwargs):
        self.temperature = 0.1
        self.azure_endpoint = ""
        self.streaming = False
        self.vision = False
        try:
            self.model_name = "gpt-4-1106-preview"
            self.llm = self._create_chat_model()
        except Exception as e:
            print(f"Failed to create chat model: {e}")
            self.model_name = "cached_response_model"
            self.llm = None
        self.streaming = False
        self.token_usage_log = TokenUsageLog("gpt-4-1106-preview")
        self.cache_file = Path(__file__).parent / "ai_cache.json"
        print(self.llm)

    def next(
        self,
        messages: List[Message],
        prompt: Optional[str | Prompt] = None,
        *,
        step_name: str,
    ) -> List[Message]:
        """
        Advances the conversation by sending message history
        to LLM and updating with the response.

        Parameters
        ----------
        messages : List[Message]
            The list of messages in the conversation.
        prompt : Optional[str], optional
            The prompt to use, by default None.
        step_name : str
            The name of the step.

        Returns
        -------
        List[Message]
            The updated list of messages in the conversation.
        """
        if  isinstance(prompt, str):
            messages.append(HumanMessage(content=prompt))
        if  isinstance(prompt, Prompt):
            messages.append(HumanMessage(content=prompt.to_langchain_content()))

        # read cache file if it exists
        if os.path.isfile(self.cache_file):
            with open(self.cache_file, "r") as cache_file:
                cache = json.load(cache_file)
        else:
            cache = dict()

        print(self.llm)
        messages_key = self.serialize_messages(messages)
        if messages_key not in cache:
            print("calling backoff inference")
            response = self.backoff_inference(messages)
            self.token_usage_log.update_log(
                messages=messages, answer=response.content, step_name=step_name
            )
            print("called backoff inference")
            print("cost in usd:", self.token_usage_log.usage_cost())

            messages.append(response)
            cache[messages_key] = self.serialize_messages(messages)
            with open(self.cache_file, "w") as cache_file:
                json.dump(cache, cache_file)
                cache_file.write("\n")

        return self.deserialize_messages(cache[messages_key])
