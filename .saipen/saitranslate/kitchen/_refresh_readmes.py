from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
KITCHEN = Path(__file__).resolve().parent
SOURCE = ROOT / "README.md"
CACHE_DIR = KITCHEN.parent / ".translation-cache"
OLLAMA_MODEL = os.environ.get("SAIPEN_TRANSLATION_MODEL", "qwen3:14b")
CACHE_CONTRACT = "structured-markdown-v2"

LOCALES = {
    "ar": "ar",
    "bg": "bg",
    "cs": "cs",
    "da": "da",
    "de": "de",
    "el": "el",
    "es": "es",
    "et": "et",
    "fi": "fi",
    "fr": "fr",
    "he": "iw",
    "hi": "hi",
    "hr": "hr",
    "hu": "hu",
    "id": "id",
    "it": "it",
    "ja": "ja",
    "ko": "ko",
    "nl": "nl",
    "no": "no",
    "pl": "pl",
    "pt": "pt",
    "ro": "ro",
    "ru": "ru",
    "sk": "sk",
    "sv": "sv",
    "th": "th",
    "tr": "tr",
    "uk": "uk",
    "vi": "vi",
    "zh": "zh-CN",
}

LANGUAGE_NAMES = {
    "ar": "Arabic", "bg": "Bulgarian", "cs": "Czech", "da": "Danish",
    "de": "German", "el": "Greek", "es": "Spanish", "et": "Estonian",
    "fi": "Finnish", "fr": "French", "iw": "Hebrew", "hi": "Hindi",
    "hr": "Croatian", "hu": "Hungarian", "id": "Indonesian",
    "it": "Italian", "ja": "Japanese", "ko": "Korean", "nl": "Dutch",
    "no": "Norwegian", "pl": "Polish", "pt": "Portuguese",
    "ro": "Romanian", "ru": "Russian", "sk": "Slovak", "sv": "Swedish",
    "th": "Thai", "tr": "Turkish", "uk": "Ukrainian", "vi": "Vietnamese",
    "zh-CN": "Simplified Chinese",
}

TOKEN_RE = re.compile(
    r"`[^`\n]+`"
    r"|(?<=\]\()[^)]+(?=\))"
    r"|https?://[^\s)>]+"
    r"|&[A-Za-z0-9#]+;"
)
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
DIGEST_RE = re.compile(r"\n*<!-- source-digest: README\.md sha256:[0-9a-f]+ -->\s*$")
MODEL_RE = re.compile(r"\n*<!-- translation-model: [^\n]+ -->\s*")
MODEL_LEAK_RE = re.compile(
    r"</?think>|\*note:|the output contains|translation includes the original json|"
    r"input json:|\['?[\w\s-]+',\s*'clone'",
    re.IGNORECASE,
)


def source_digest(text: str) -> str:
    return hashlib.sha256(VERSION_RE.sub("VERSION", text).encode("utf-8")).hexdigest()


def protected_source(text: str) -> tuple[str, dict[str, str]]:
    protected: dict[str, str] = {}
    in_fence = False
    output: list[str] = []

    def reserve(value: str) -> str:
        token = f"[[[P{len(protected):05d}]]]"
        protected[token] = value
        return token

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            output.append(reserve(line))
            continue
        if in_fence or line.lstrip().startswith(("<", "[![")):
            output.append(reserve(line))
            continue
        output.append(TOKEN_RE.sub(lambda match: reserve(match.group(0)), line))
    return "\n".join(output), protected


def chunks(text: str, limit: int = 3400) -> list[str]:
    lines = text.splitlines()
    result: list[str] = []
    current: list[str] = []
    size = 0
    for line in lines:
        extra = len(line) + (1 if current else 0)
        if current and size + extra > limit:
            result.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += extra
    if current:
        result.append("\n".join(current))
    return result


def google_translate(text: str, target: str) -> str:
    payload = urllib.parse.urlencode(
        {"client": "at", "sl": "en", "tl": target, "dt": "t", "q": text}
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://translate.googleapis.com/translate_a/single",
        data=payload,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            translated = "".join(part[0] for part in data[0] if part[0] is not None)
            time.sleep(0.6)
            return translated
        except Exception as exc:  # network/rate limiting: bounded retry
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"translation failed for {target}: {last_error}")


def ollama_translate(
    text: str, target: str, *, angry: bool = False, model: str = OLLAMA_MODEL
) -> str:
    voice = (
        " Use an angry-grandpa voice: blunt, compressed, mildly mocking, but "
        "factually exact."
        if angry
        else ""
    )
    prompt = (
        f"Translate the following English Markdown into {target}.{voice} Return "
        "only the translated Markdown. Preserve every [[[P00000]]]-shaped "
        "placeholder exactly, including its number and brackets. Do not add a "
        "preamble or explanation.\n\n" + text
    )
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 4096},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        data = json.loads(response.read().decode("utf-8"))
    result = data.get("response", "")
    if not result:
        raise RuntimeError(f"Ollama returned no {target} translation")
    if MODEL_LEAK_RE.search(result):
        raise RuntimeError(f"Ollama leaked model commentary into {target} translation")
    return result


def ollama_translate_segments(segments: list[str], target: str) -> list[str]:
    cache_key = hashlib.sha256(
        (
            CACHE_CONTRACT
            + "\0"
            + OLLAMA_MODEL
            + "\0"
            + target
            + "\0"
            + json.dumps(segments, ensure_ascii=False)
        ).encode("utf-8")
    ).hexdigest()
    cache_path = CACHE_DIR / target.replace(" ", "_") / f"{cache_key}.json"
    if cache_path.is_file():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(cached, list) and len(cached) == len(segments):
            return [str(item) for item in cached]
    schema = {
        "type": "object",
        "properties": {
            "translations": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": len(segments),
                "maxItems": len(segments),
            }
        },
        "required": ["translations"],
        "additionalProperties": False,
    }
    prompt = (
        f"Translate each JSON array item from English into {target}. Return one "
        "translation per input item, in identical order. Preserve Markdown "
        "punctuation, SAIPEN, file paths, and command names. Translate prose, "
        "not technical identifiers. No explanations. Input JSON:\n"
        + json.dumps(segments, ensure_ascii=False)
    )
    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 4096},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        data = json.loads(response.read().decode("utf-8"))
    try:
        result = json.loads(data.get("response", "{}"))
        translations = result.get("translations", [])
    except (json.JSONDecodeError, AttributeError):
        translations = []
    if len(translations) != len(segments):
        if len(segments) == 1:
            return [ollama_translate(segments[0], target)]
        middle = len(segments) // 2
        return ollama_translate_segments(segments[:middle], target) + ollama_translate_segments(
            segments[middle:], target
        )
    normalized = [str(item).strip() for item in translations]
    if any(MODEL_LEAK_RE.search(item) for item in normalized):
        normalized = [
            ollama_translate(item, target, model=OLLAMA_MODEL) for item in segments
        ]
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(normalized, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return normalized


def translate_document_structured(source: str, target: str) -> str:
    masked, protected = protected_source(source)
    token_pattern = r"(\[\[\[P\d{5}\]\]\])"
    markup_pattern = r"(\*\*|__|\||\[|\]|\(|\))"
    pieces: list[str] = []
    for line in masked.splitlines(keepends=True):
        newline = "\n" if line.endswith("\n") else ""
        body = line[:-1] if newline else line
        line_parts = re.split(token_pattern, body)
        for part_index, raw_part in enumerate(line_parts):
            if re.fullmatch(token_pattern, raw_part):
                pieces.append(raw_part)
                continue
            prefix = ""
            prose_part = raw_part
            if part_index == 0:
                match = re.match(r"^(\s*(?:#{1,6}|[-+*>]|\d+\.)\s+)", prose_part)
                if match:
                    prefix = match.group(1)
                    prose_part = prose_part[match.end() :]
            if prefix:
                pieces.append(prefix)
            pieces.extend(re.split(markup_pattern, prose_part))
        if newline:
            pieces.append(newline)
    indexes = [
        index
        for index, piece in enumerate(pieces)
        if not re.fullmatch(token_pattern, piece)
        and not re.fullmatch(markup_pattern, piece)
        and piece != "\n"
        and re.search(r"[A-Za-z]{2}", piece)
    ]
    originals = [pieces[index] for index in indexes]
    translated: list[str] = []
    for start in range(0, len(originals), 12):
        translated.extend(ollama_translate_segments(originals[start : start + 12], target))
    for index, translated_value in zip(indexes, translated, strict=True):
        cleaned_value = re.sub(token_pattern, "", translated_value)
        cleaned_value = cleaned_value.replace("\r", " ").replace("\n", " ").replace("```", "")
        pieces[index] = cleaned_value
    for index, piece in enumerate(pieces):
        if piece in protected:
            pieces[index] = protected[piece]
    rebuilt = "".join(pieces)
    if re.search(token_pattern, rebuilt):
        raise RuntimeError(f"translation hallucinated a placeholder for {target}")
    return rebuilt


def translate_line(line: str, target: str) -> str:
    pieces = re.split(r"(\[\[\[P\d{5}\]\]\])", line)
    output: list[str] = []
    for piece in pieces:
        if not piece or re.fullmatch(r"\[\[\[P\d{5}\]\]\]", piece):
            output.append(piece)
        elif re.search(r"[A-Za-z]{2}", piece):
            output.append(google_translate(piece, target))
        else:
            output.append(piece)
    return "".join(output)


def translate_document(source: str, target: str, *, ollama: bool = False) -> str:
    masked, protected = protected_source(source)
    translated_chunks: list[str] = []
    for chunk in chunks(masked):
        used_local = ollama
        if ollama:
            translated_chunk = ollama_translate(chunk, target, angry=True)
        else:
            try:
                translated_chunk = google_translate(chunk, target)
            except RuntimeError:
                used_local = True
                translated_chunk = ollama_translate(chunk, LANGUAGE_NAMES[target])
        expected = set(re.findall(r"\[\[\[P\d{5}\]\]\]", chunk))
        if any(translated_chunk.count(token) != 1 for token in expected):
            if used_local:
                local_target = target if ollama else LANGUAGE_NAMES[target]
                translated_chunk = ollama_translate(
                    chunk,
                    local_target,
                    angry=ollama,
                    model="qwen3:14b",
                )
            else:
                translated_chunk = "\n".join(
                    translate_line(line, target) for line in chunk.splitlines()
                )
        translated_chunks.append(translated_chunk)
    translated = "\n".join(translated_chunks)
    for token, value in protected.items():
        count = translated.count(token)
        if count != 1:
            raise RuntimeError(f"placeholder {token} survived {count} times for {target}")
        translated = translated.replace(token, value)
    return translated


def finalize(text: str, digest: str) -> str:
    text = DIGEST_RE.sub("", text.rstrip())
    text = MODEL_RE.sub("", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    if MODEL_LEAK_RE.search(text):
        raise RuntimeError("translation contains model commentary")
    return (
        f"{text}\n\n<!-- translation-model: {OLLAMA_MODEL} contract:{CACHE_CONTRACT} -->\n"
        f"<!-- source-digest: README.md sha256:{digest} -->\n"
    )


def structurally_current(path: Path, source: str, digest: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8-sig")
    return (
        f"sha256:{digest} -->" in text
        and f"translation-model: {OLLAMA_MODEL} contract:{CACHE_CONTRACT}" in text
        and len(re.findall(r"^```", text, re.MULTILINE))
        == len(re.findall(r"^```", source, re.MULTILINE))
        and len(re.findall(r"^## ", text, re.MULTILINE))
        == len(re.findall(r"^## ", source, re.MULTILINE))
        and len(re.findall(r"^\|", text, re.MULTILINE))
        == len(re.findall(r"^\|", source, re.MULTILINE))
        and not re.search(r"ZXQ|\[\[\[P\d", text)
        and not MODEL_LEAK_RE.search(text)
        and not any(line != line.rstrip() for line in text.splitlines())
    )


def sync_shortcut_callouts() -> None:
    core_mirrors = {
        "ded": ROOT / "README.ded.md",
        "et": ROOT / "README.ee.md",
        "ja": ROOT / "README.ja.md",
    }
    for locale in sorted(set(LOCALES) | {"ded"}):
        source_path = core_mirrors.get(locale, ROOT / "guides" / f"GUIDE_{locale.upper()}.md")
        source_lines = source_path.read_text(encoding="utf-8-sig").splitlines()
        callouts = [
            line for line in source_lines if "#110-command-surface" in line and "`cc`" in line
        ]
        if len(callouts) != 1:
            raise RuntimeError(f"{source_path} has {len(callouts)} shortcut callouts")
        callout = callouts[0].replace(
            "](../saipen/RFC.md#110-command-surface)",
            "](saipen/RFC.md#110-command-surface)",
        )
        output = KITCHEN / locale / f"README_{locale.upper()}.md"
        lines = output.read_text(encoding="utf-8-sig").splitlines()
        matches = [
            index
            for index, line in enumerate(lines)
            if "#110-command-surface" in line and "`cc`" in line
        ]
        if len(matches) != 1:
            raise RuntimeError(f"{output} has {len(matches)} shortcut callouts")
        lines[matches[0]] = callout
        output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    source = SOURCE.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    digest = source_digest(source)
    ded_output = KITCHEN / "ded" / "README_DED.md"
    ded_cache = KITCHEN / ".ded_source_digest"
    cache_proof = f"{digest} {OLLAMA_MODEL} {CACHE_CONTRACT}"
    if (
        not args.force
        and ded_cache.is_file()
        and ded_cache.read_text(encoding="utf-8").strip() == cache_proof
        and structurally_current(ded_output, source, digest)
    ):
        print("ded: current (cache proof)", flush=True)
    else:
        body = translate_document(source, "Russian", ollama=True)
        ded_output.write_text(finalize(body, digest), encoding="utf-8", newline="\n")
        ded_cache.write_text(cache_proof + "\n", encoding="utf-8", newline="\n")
        print(f"ded: translated -> {ded_output.name}", flush=True)
    for locale, target in LOCALES.items():
        output = KITCHEN / locale / f"README_{locale.upper()}.md"
        if not args.force and structurally_current(output, source, digest):
            print(f"{locale}: current (cache proof)", flush=True)
            continue
        body = translate_document_structured(source, LANGUAGE_NAMES[target])
        output.write_text(finalize(body, digest), encoding="utf-8", newline="\n")
        print(f"{locale}: translated -> {output.name}", flush=True)
    sync_shortcut_callouts()
    print("shortcut-callouts: synced from maintained guide/mirror sources", flush=True)
    print(f"digest={digest}", flush=True)


if __name__ == "__main__":
    main()
