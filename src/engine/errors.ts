/** An invalid value, as Python's ValueError: the port raises where the Python engine does. */
export class ValueError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ValueError';
  }
}

/** An operation not allowed in the current state, as Python's RuntimeError (e.g. resolving a finished battle). */
export class RuntimeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'RuntimeError';
  }
}
