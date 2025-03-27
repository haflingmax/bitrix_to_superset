export interface ServiceStatus {
    backend: {
      status: "running" | "down" | "unknown";
      error?: string;
    };
    bitrix24: {
      available: boolean;
      license: string;
      scopes: string[];
      error?: string;
    };
  }