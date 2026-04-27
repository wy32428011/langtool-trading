import json

import requests
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from openai import OpenAI

from agent import Agent
from config import settings


def _requests_call(prompt: str, llm_base_url: str, llm_model: str, llm_api_key: str, llm_temperature: float) -> dict:
    payload = {
        'model': llm_model,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': llm_temperature,
        'max_tokens': 128,
        'stream': True,
    }
    response = requests.post(
        f'{llm_base_url}/chat/completions',
        headers={
            'Authorization': f'Bearer {llm_api_key}',
            'Content-Type': 'application/json',
        },
        json=payload,
        timeout=60,
        stream=True,
    )
    text_parts = []
    raw = []
    for line in response.iter_lines():
        if not line:
            continue
        decoded = line.decode('utf-8') if isinstance(line, bytes) else str(line)
        if not decoded.startswith('data: '):
            continue
        data = decoded[6:]
        if data == '[DONE]':
            break
        body = json.loads(data)
        raw.append(body)
        choices = body.get('choices') or []
        if not choices:
            continue
        delta = choices[0].get('delta', {}) or {}
        content = delta.get('content')
        if isinstance(content, str) and content:
            text_parts.append(content)
    return {
        'ok': response.ok,
        'content': ''.join(text_parts),
        'raw': raw,
    }


def _openai_sdk_call(prompt: str, llm_base_url: str, llm_model: str, llm_api_key: str, llm_temperature: float) -> dict:
    client = OpenAI(base_url=llm_base_url, api_key=llm_api_key)
    response = client.chat.completions.create(
        model=llm_model,
        messages=[{'role': 'user', 'content': prompt}],
        temperature=llm_temperature,
        max_tokens=128,
        stream=True,
    )
    text_parts = []
    raw = []
    for chunk in response:
        raw.append(chunk)
        choices = getattr(chunk, 'choices', None) or []
        if not choices:
            continue
        delta = getattr(choices[0], 'delta', None)
        content = getattr(delta, 'content', None) if delta else None
        if isinstance(content, str) and content:
            text_parts.append(content)
    content = ''.join(text_parts)
    return {
        'ok': True,
        'content': content,
        'raw': raw,
    }


def _langchain_call(prompt: str, llm_base_url: str, llm_model: str, llm_api_key: str, llm_temperature: float) -> dict:
    if (
        llm_base_url == settings.llm_base_url
        and llm_model == settings.llm_model
        and llm_api_key == settings.llm_api_key
        and llm_temperature == settings.llm_temperature
    ):
        agent = Agent()
        content = agent.stream_messages_text([HumanMessage(content=prompt)])
    else:
        model = ChatOpenAI(
            base_url=llm_base_url,
            model=llm_model,
            api_key=llm_api_key,
            max_tokens=settings.max_tokens,
            temperature=llm_temperature,
            streaming=True,
        )
        text_parts = []
        for chunk in model.stream([HumanMessage(content=prompt)]):
            text = getattr(chunk, 'text', None)
            if isinstance(text, str) and text:
                text_parts.append(text)
                continue
            chunk_content = getattr(chunk, 'content', '')
            if isinstance(chunk_content, str) and chunk_content:
                text_parts.append(chunk_content)
        content = ''.join(text_parts)
    raw = {
        'content': content,
    }
    return {
        'ok': True,
        'content': content or '',
        'raw': raw,
    }


def _safe_collect(callable_obj, *args) -> dict:
    try:
        return callable_obj(*args)
    except Exception as exc:
        return {
            'ok': False,
            'content': '',
            'raw': {
                'error_type': type(exc).__name__,
                'error': str(exc),
            },
        }


def collect_llm_transport_results(prompt: str, config_override: dict | None = None) -> dict:
    config_override = config_override or {}
    llm_base_url = config_override.get('llm_base_url', settings.llm_base_url)
    llm_model = config_override.get('llm_model', settings.llm_model)
    llm_api_key = config_override.get('llm_api_key', settings.llm_api_key)
    llm_temperature = config_override.get('llm_temperature', settings.llm_temperature)
    return {
        'requests': _safe_collect(_requests_call, prompt, llm_base_url, llm_model, llm_api_key, llm_temperature),
        'openai_sdk': _safe_collect(_openai_sdk_call, prompt, llm_base_url, llm_model, llm_api_key, llm_temperature),
        'langchain': _safe_collect(_langchain_call, prompt, llm_base_url, llm_model, llm_api_key, llm_temperature),
    }


def collect_multi_config_results(prompt: str, configs: list[dict]) -> dict:
    result = {}
    for config in configs:
        result[config['name']] = collect_llm_transport_results(prompt, config)
    return result
