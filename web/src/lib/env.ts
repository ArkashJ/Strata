// Zod-validated client/server env. Import `env` instead of reading
// `process.env` directly anywhere in app code.
import { z } from "zod";

const ServerEnv = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
});

const ClientEnv = z.object({
  NEXT_PUBLIC_API_URL: z.string().url().default("http://localhost:8000"),
});

const parsedServer = ServerEnv.safeParse({ NODE_ENV: process.env.NODE_ENV });
if (!parsedServer.success) {
  throw new Error(`Invalid server env: ${parsedServer.error.message}`);
}

const parsedClient = ClientEnv.safeParse({
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
});
if (!parsedClient.success) {
  throw new Error(`Invalid client env: ${parsedClient.error.message}`);
}

export const env = { ...parsedServer.data, ...parsedClient.data };
