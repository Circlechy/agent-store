def recursive_format(data, inputs):
    """
    Recursively finds and replaces {{variable}} in strings,
    dicts, and lists.
    """
    if isinstance(data, str):
        # Basic mustache replacement
        for key, value in inputs.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in data:
                data = data.replace(placeholder, str(value))
        return data
    elif isinstance(data, dict):
        return {k: recursive_format(v, inputs) for k, v in data.items()}
    elif isinstance(data, list):
        return [recursive_format(i, inputs) for i in data]
    return data

def patched_build_user_prompt_content(self, inputs: dict) -> list[dict]:
    # Get the user prompt list from the config
    template_content_list = self._config.template_content
    user_prompts = [element for element in template_content_list if element.get("role", "") == "user"]

    if not user_prompts:
        return []

    # Apply recursive formatting to the content field of the user message
    # Most frameworks store the content as a list of dicts (text/image_url)
    content = user_prompts[0].get("content", [])
    formatted_content = recursive_format(content, inputs)

    # Return in the format the LLM expects
    return [{"role": "user", "content": formatted_content}]


def patched_build_system_prompt(self, inputs: dict):
    system_prompts = []
    for element in self._config.template_content:
        if element.get("role", "") == "system":
            system_prompts.append(element)
        else:
            break
    return recursive_format(system_prompts, inputs)


# --- Apply the Monkey Patch ---
# LLMExecutable._build_user_prompt_content = patched_build_user_prompt_content
# LLMExecutable._build_system_prompt = patched_build_system_prompt

# print("Successfully patched LLMExecutable for nested interpolation.")