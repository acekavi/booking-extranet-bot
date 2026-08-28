import type { SourceConfig } from "../config.js";
import { JsonPriceSource } from "./json.js";
import { PostgresPriceSource } from "./postgres.js";
import type { PriceSource } from "./types.js";

export function createPriceSource(config: SourceConfig): PriceSource {
  switch (config.type) {
    case "json":
      return new JsonPriceSource(config.pricesPath, config.bookingsPath);
    case "postgres": {
      const connectionString = process.env[config.connectionStringEnv];
      if (!connectionString) {
        throw new Error(
          `$${config.connectionStringEnv} is not set. Put it in .env (which is gitignored) ` +
            `or export it before running.`
        );
      }
      return new PostgresPriceSource(connectionString, config.pricesQuery, config.bookingsQuery);
    }
  }
}

export type { Booking, PriceSource, PriceTable } from "./types.js";
