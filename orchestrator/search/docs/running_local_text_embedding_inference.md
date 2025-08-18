# Running a local MiniLM embedding server with Hugging Face TEI

Only **OpenAI-compatible endpoints** are supported. Most providers are, including local solutions.

You can spin up a embedding API based on **sentence-transformers/all-MiniLM-L6-v2** using [Hugging Face TEI](https://github.com/huggingface/text-embeddings-inference):

```bash
docker run --rm -p 8080:80 ghcr.io/huggingface/text-embeddings-inference:cpu-1.8 \
    --model-id sentence-transformers/all-MiniLM-L6-v2
```

---

## Environment variables

Point your backend to the local endpoint and declare the new vector size:

```env
EMBEDDING_MODEL=openai/tei # "tei" can be anything.
OPENAI_BASE_URL=http://localhost:8080/v1
EMBEDDING_DIMENSION=384
```

---

## Apply the schema change

Changing the dimension truncates `ai_search_index`.

Make sure you re-index afterwards.

### Step back to the revision right before the dynamic-dimension migration

```bash
dotenv run python main.py db downgrade 850dccac3b02
```

### Upgrade to the latest head (this will truncate and alter the embedding column):

```bash
dotenv run python main.py db upgrade heads
```

---

## Re-index embeddings

```bash
dotenv run python main.py index subscriptions
```

The search index now uses **384-dimension MiniLM vectors** served from your local Docker container. That’s it! 🚀
