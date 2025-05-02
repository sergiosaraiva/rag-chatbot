import os
import re
import argparse
from typing import List
from openai import OpenAI
import tiktoken

# ──────── Utility: Token counting & chunking ────────

def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Return number of tokens in text for a given encoding."""
    enc = tiktoken.get_encoding(encoding_name)
    return len(enc.encode(text))

def chunk_text_by_tokens(text: str,
                         max_tokens: int,
                         encoding_name: str = "cl100k_base") -> List[str]:
    """
    Split `text` into chunks each ≤ max_tokens (by true token count),
    preserving paragraph boundaries.
    """
    paras = text.split("\n\n")
    chunks: List[str] = []
    current = ""
    current_count = 0

    for p in paras:
        piece = p.strip() + "\n\n"
        pc = count_tokens(piece, encoding_name)
        if current_count + pc > max_tokens:
            if current:
                chunks.append(current.strip())
            # If a single paragraph is _itself_ too big, force-split by character
            if pc > max_tokens:
                # fallback: naive split
                for i in range(0, len(piece),  max_tokens * 4):
                    seg = piece[i : i + max_tokens * 4]
                    chunks.append(seg.strip())
                current = ""
                current_count = 0
                continue
            current = piece
            current_count = pc
        else:
            current += piece
            current_count += pc

    if current:
        chunks.append(current.strip())
    return chunks

# ──────── Summarization ────────

def summarize_chunk(client: OpenAI,
                    text: str,
                    model: str,
                    max_tokens: int) -> str:
    """Call OpenAI to summarize a single chunk."""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system",  "content": "You are a helpful assistant that summarizes text."},
            {"role": "user",    "content": f"Please provide a concise summary of the following text:\n\n{text}"}
        ],
        temperature=0.3,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()

def hierarchical_summary(client: OpenAI,
                         text: str,
                         model: str,
                         chunk_size: int = 24000,
                         summary_tokens: int = 512) -> str:
    """
    If `text` is too big, chunk & summarize each piece, then
    summarize the concatenation of those summaries.
    """
    # Count tokens; if under model window, do one-shot
    total_tokens = count_tokens(text)
    if total_tokens <= chunk_size:
        return summarize_chunk(client, text, model, summary_tokens)

    # 1) Chunk
    chunks = chunk_text_by_tokens(text, max_tokens=chunk_size)
    # 2) Summarize each chunk
    summaries = []
    for idx, c in enumerate(chunks, start=1):
        print(f"  ● Summarizing chunk {idx}/{len(chunks)} ({count_tokens(c)} tokens)…")
        summaries.append(summarize_chunk(client, c, model, summary_tokens))
    # 3) Combine & re-summarize
    combined = "\n\n".join(summaries)
    print("  ● Summarizing combined chunk summaries…")
    return summarize_chunk(client, combined, model, summary_tokens)

# ──────── File I/O ────────

def collapse_newlines(text: str) -> str:
    return re.sub(r"\n{2,}", "\n\n", text)

def split_sections(text: str, sep_pattern: str) -> List[tuple]:
    pattern = re.compile(sep_pattern, flags=re.MULTILINE)
    parts   = pattern.split(text)
    headers = pattern.findall(text)
    sections = []
    if parts[0].strip():
        sections.append(("", parts[0].strip()))
    for i, hdr in enumerate(headers, start=1):
        body = parts[i].strip() if i < len(parts) else ""
        sections.append((hdr.strip(), body))
    return sections

def write_section_file(output_dir: str, base_name: str, idx: int,
                       full_summary: str, header: str,
                       section_summary: str, section_text: str):
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", header) if header else f"part{idx}"
    fn   = f"{base_name}_{idx:02d}_{safe}.txt"
    path = os.path.join(output_dir, fn)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Document Summary\n")
        f.write(full_summary + "\n\n")
        f.write(f"# Section: {header or 'Untitled'}\n")
        f.write("## Section Summary\n")
        f.write(section_summary + "\n\n")
        f.write("## Section Text\n")
        f.write(section_text + "\n")
    print(f"→ Wrote {path}")

# ──────── Main ────────

def main():
    p = argparse.ArgumentParser(description="Prepare text for RAG (chunked + G4-32k).")
    p.add_argument("input_file", help="Raw .txt document")
    p.add_argument("output_dir",  help="Where to dump section files")
    p.add_argument(
      "--separator",
      default=r"(?m)^CAPITULO .+",
      help="Regex for splitting sections"
    )
    p.add_argument(
      "--model",
      default="gpt-4-32k",
      help="OpenAI model (e.g. gpt-4-32k)."
    )
    p.add_argument(
      "--chunk-tokens",
      type=int,
      default=24000,
      help="Max tokens per chunk (≲ model window)."
    )
    p.add_argument(
      "--summary-tokens",
      type=int,
      default=512,
      help="Tokens to allocate for each summary call."
    )
    args = p.parse_args()

    # Init client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if not client.api_key:
        raise RuntimeError("Set OPENAI_API_KEY in your env first.")

    os.makedirs(args.output_dir, exist_ok=True)
    raw = open(args.input_file, "r", encoding="utf-8").read()
    text = collapse_newlines(raw)

    print("=== Generating full document summary ===")
    full_sum = hierarchical_summary(
        client,
        text,
        model=args.model,
        chunk_size=args.chunk_tokens,
        summary_tokens=args.summary_tokens
    )

    print("=== Splitting into sections ===")
    sections = split_sections(text, args.separator)
    base     = os.path.splitext(os.path.basename(args.input_file))[0]

    for i, (hdr, sec_text) in enumerate(sections, start=1):
        print(f"\n--- Section {i}: “{hdr or 'Untitled'}” ---")
        sec_sum = summarize_chunk(client, sec_text, args.model, args.summary_tokens)
        write_section_file(
            args.output_dir, base, i,
            full_sum, hdr, sec_sum, sec_text
        )

if __name__ == "__main__":
    main()
