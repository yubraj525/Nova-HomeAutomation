from app.tts.tts_engine import synthesize_to_chunks


def main():
    text = "नमस्ते, आज मौसम राम्रो छ। How are you today?"

    for chunk in synthesize_to_chunks(text):
        print(
            f"Sequence: {chunk.sequence} | "
            f"Bytes: {len(chunk.data)} | "
            f"Duration: {chunk.duration:.3f}s"
        )


if __name__ == "__main__":
    main()