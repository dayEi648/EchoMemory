export type TokenPair = {
  accessToken: string;
  refreshToken: string;
};

export type TokenStore = {
  get: () => TokenPair | null;
  set: (tokens: TokenPair) => void;
  clear: () => void;
};

export const createMemoryTokenStore = (initial: TokenPair | null = null): TokenStore => {
  let current = initial;
  return {
    get: () => current,
    set: (tokens) => {
      current = tokens;
    },
    clear: () => {
      current = null;
    },
  };
};

export const createLocalStorageTokenStore = (key = "echomemory_tokens"): TokenStore => {
  return {
    get: () => {
      try {
        const raw = localStorage.getItem(key);
        if (!raw) return null;
        return JSON.parse(raw) as TokenPair;
      } catch {
        return null;
      }
    },
    set: (tokens) => {
      localStorage.setItem(key, JSON.stringify(tokens));
    },
    clear: () => {
      localStorage.removeItem(key);
    },
  };
};
