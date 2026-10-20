# Web

A Next.js chat interface for the RAG service. It streams answers from the API and shows retrieval progress, the answer as it is generated, and its citations.

## Structure

| Path | Description |
|---|---|
| `app/page.tsx` | Chat UI |
| `app/api/v1/chat/stream/route.ts` | Proxies the request to the FastAPI streaming endpoint and passes Server-Sent Events through unbuffered |
| `lib/sse.ts` | Parses the Server-Sent Events stream on the client |

## Running Locally

Start the API first (see `apps/api/README.md`), then:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The API URL defaults to `http://localhost:8000`. Set `NEXT_PUBLIC_API_BASE_URL` to point to a different backend.
