import os
import re
import argparse
import openai
from typing import List


def collapse_newlines(text: str) -> str:
    """
    Collapse multiple consecutive blank lines into a single blank line.
    """
    # Replace 2 or more newline characters with exactly two (one blank line)
    return re.sub(r"\n{2,}", "\n\n", text)


def split_sections(text: str, sep_pattern: str) -> List[tuple]:
    """
    Split the text into sections using a separator regex pattern.
    Returns a list of tuples (section_header, section_text).
    The first header may be an empty string if text before first separator exists.
    """
    # Compile regex for multiline matching
    pattern = re.compile(sep_pattern, flags=re.MULTILINE)
    # Split, keeping the separators
    parts = pattern.split(text)
    # Find all separator matches
    headers = pattern.findall(text)
    sections = []
    # If there's leading text before first header
    if parts[0].strip():
        sections.append(("", parts[0].strip()))
    # Each header corresponds to the following body in parts
    for idx, header in enumerate(headers, start=1):
        body = parts[idx].strip() if idx < len(parts) else ''
        sections.append((header.strip(), body))
    return sections


def summarize(text: str, model: str = "gpt-3.5-turbo", max_tokens: int = 512) -> str:
    """
    Use OpenAI ChatCompletion to generate a concise summary of the input text.
    """
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("Please set the OPENAI_API_KEY environment variable.")

    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes documents."},
            {"role": "user", "content": f"Please provide a concise summary of the following text:\n\n{text}"}
        ],
        temperature=0.3,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def write_section_file(output_dir: str, base_name: str, index: int,
                       full_summary: str, section_header: str,
                       section_summary: str, section_text: str):
    """
    Write out a single section file with summaries and raw text.
    """
    # Sanitize header for filename
    safe_header = re.sub(r"[^0-9A-Za-z_-]", "_", section_header) if section_header else f"part{index}"
    filename = f"{base_name}_{index:02d}_{safe_header}.txt"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Document Summary\n")
        f.write(full_summary + "\n\n")
        f.write(f"# Section: {section_header or 'Untitled'}\n")
        f.write("## Section Summary\n")
        f.write(section_summary + "\n\n")
        f.write("## Section Text\n")
        f.write(section_text + "\n")
    print(f"Written section file: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Prepare text documents for RAG by summarizing and splitting into sections."
    )
    parser.add_argument("input_file", help="Path to the input text document.")
    parser.add_argument("output_dir", help="Directory to output section files.")
    parser.add_argument(
        "--separator",
        default=r"(?m)^CAPITULO .+",
        help="Regex pattern to split sections (multiline)."
    )
    parser.add_argument(
        "--model",
        default="gpt-3.5-turbo",
        help="OpenAI model to use for summarization."
    )
    args = parser.parse_args()

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    # Read and preprocess document
    with open(args.input_file, "r", encoding="utf-8") as infile:
        raw_text = infile.read()
    collapsed = collapse_newlines(raw_text)

    # Summarize entire document
    print("Generating full document summary...")
    full_summary = summarize(collapsed, model=args.model)

    # Split into sections
    sections = split_sections(collapsed, args.separator)

    # Process each section
    base_name = os.path.splitext(os.path.basename(args.input_file))[0]
    for idx, (header, text) in enumerate(sections, start=1):
        print(f"Processing section {idx}: {header or '<no header>'}...")
        section_summary = summarize(text, model=args.model)
        write_section_file(
            args.output_dir, base_name, idx,
            full_summary, header, section_summary, text
        )

if __name__ == "__main__":
    main()
