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
