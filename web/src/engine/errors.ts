/** An invalid value, as Python's ValueError: the port raises where the Python engine does. */
export class ValueError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ValueError';
  }
}
