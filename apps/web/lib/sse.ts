export type SseEvent = {
  event: string;
  data: unknown;
};

export async function* streamSse(
  url: string,
  init: RequestInit,
): AsyncGenerator<SseEvent> {
  const response = await fetch(url, init);
  if (!response.ok || !response.body) {
    throw new Error(`Stream request failed: ${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex: number;
    while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      const parsed = parseSseBlock(rawEvent);
      if (parsed) yield parsed;
    }
  }

  if (buffer.trim().length > 0) {
    const parsed = parseSseBlock(buffer);
    if (parsed) yield parsed;
  }
}

function parseSseBlock(block: string): SseEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (dataLines.length === 0) return null;
  const dataString = dataLines.join("\n");
  try {
    return { event, data: JSON.parse(dataString) };
  } catch {
    return { event, data: dataString };
  }
}
