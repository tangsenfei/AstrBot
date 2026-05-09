declare module 'event-source-polyfill' {
  export class EventSourcePolyfill {
    constructor(url: string, options?: Record<string, any>);
    onopen: ((event: Event) => void) | null;
    onerror: ((event: Event) => void) | null;
    addEventListener(type: string, listener: (event: MessageEvent) => void): void;
    close(): void;
  }
}
