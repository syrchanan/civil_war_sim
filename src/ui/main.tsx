import { render } from 'preact';

import { App } from './App';
import { createStore, modeFromUrl } from './store';
import './style.css';

// the player view by default; ?mode=admin opens the admin view
render(<App store={createStore(undefined, modeFromUrl(window.location.search))} />, document.getElementById('app')!);
