import { render } from 'preact';

import { App } from './App';
import { createStore, modeFromUrl } from './store';
// the style A typefaces, bundled with the site (OFL): display face and body face
import '@fontsource/im-fell-english-sc/latin-400.css';
import '@fontsource-variable/source-serif-4/opsz.css';
import '@fontsource-variable/source-serif-4/opsz-italic.css';
import './style.css';

// the player view by default; ?mode=admin opens the admin view
render(<App store={createStore(undefined, modeFromUrl(window.location.search))} />, document.getElementById('app')!);
