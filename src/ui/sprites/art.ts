/**
 * Pixel art for the unit vignette, drawn facing right. One character per pixel; '.' is clear; 'S', 'U' and 'K' are
 * the side's coat, trousers and cap (palette.ts UNIFORMS); every other letter a palette colour. Rows may be ragged:
 * missing pixels are clear.
 */

export type Grid = string[];

const g = (s: string): Grid => s.replace(/^\n/, '').replace(/\n$/, '').split('\n');

// --- infantry -------------------------------------------------------------------------------------------------

/** Order arms: musket upright at his side. */
export const SOLDIER_IDLE = g(`
.......m
...KKK.m
..KKKK.m
..KKKkkm
..fff..m
..ff...m
.SSSS..m
SSSSSSfm
SSSSSS.m
.SSSS..m
.kkkc..w
.SSSS..w
.UUUU..w
.UU.UU.w
.UU.UU.w
.UU.UU.w
.kk.kk.w`);

/** Taking aim; the muzzle is at (13, 5). */
export const SOLDIER_AIM = g(`
..............
...KKK........
..KKKK........
..KKKkk.......
..fff.........
.wwffmmmmmmmmm
.SSSSfS.......
SSSSSS........
SSSSSS........
.SSSS.........
.kkkc.........
.SSSS.........
.UUUU.........
.UU..UU.......
.UU...UU......
.UU...UU......
.kk...kkk.....`);

const LEANING = `
...............
.....KKK.......
....KKKK.......
....KKKkk......
....fff........
...SSSf........
..SSSSSS.......
.SSSSSSf.......
.wwSSSSmmmmmmmm
..SSSS.........
..kkkc.........
..UUUU.........`;

const RUNNING = `
...............
.....KKK.......
....KKKK.......
....KKKkk......
....fff..f.....
...SSSf.f......
..SSSSSSf......
fSSSSSS........
.SSSSSS........
..SSSS.........
..kkkc.........
..UUUU.........`;

const STRIDE_A = `
.UU..UU........
UU....UU.......
U......UU......
k.......kk.....`;

const STRIDE_B = `
..UUUU.........
...UU.U........
..UU..U........
..kk..kk.......`;

const PLANTED = `
.UU...UU.......
.UU...UU.......
.UU...UU.......
.kk...kkk......`;

/** Bayonet levelled at the run (two strides); the point is at (14, 8). */
export const SOLDIER_CHARGE = [g(LEANING + STRIDE_A), g(LEANING + STRIDE_B)];
/** Bayonet levelled, feet planted: thrust and recover. */
export const SOLDIER_THRUST = g(LEANING + PLANTED);
/** Running away, musket thrown down (two strides). */
export const SOLDIER_RUN = [g(RUNNING + STRIDE_A), g(RUNNING + STRIDE_B)];
/** A gunner: the idle soldier with a rammer for a musket. */
export const GUNNER = SOLDIER_IDLE.map((row) => row.replace(/m/g, 'w'));

// --- cavalry --------------------------------------------------------------------------------------------------

const HORSE_BODY = `
..................kk..
.................hhhk.
................hhhhhh
...............hhhhhHh
..............hhhh..HH
..hhhhSSSSShhhhh......
.hhhhhSSSSShhhhh......
HhhhhhhhhhhhhhhH......
H.hhhhhhhhhhhhh.......`;

export const HORSE_STAND = g(HORSE_BODY + `
H.hh.hh.....hh.hh.....
..hh.hh.....hh.hh.....
..hh.hh.....hh.hh.....
..kk.kk.....kk.kk.....`);

/** At the gallop: stretched out, then gathered. */
export const HORSE_GALLOP = [
  g(HORSE_BODY + `
.hh...........hh......
hh..............hh....
k.................kk..`),
  g(HORSE_BODY + `
...hhhh....hhhh.......
....hh.hh..hh.hh......
....kk..kk.kk..k......`),
];

/** In the saddle; the thigh (row 8) sits on the horse's back (its row 5). */
export const RIDER = g(`
...KKK...
..KKKK...
..KKKkk..
..fff....
..ff.....
.SSSS....
SSSSSS...
SSSSSS...
.UUUUU...
..UUUU...
...kk....`);

/** Sabre sloped over the shoulder. */
export const SABRE_SLOPE = g(`
...m
..m.
.m..
f...`);

/** Sabre at the point, arm out. */
export const SABRE_POINT = g('SSfmmmmmmm');

/** Sabre raised to cut. */
export const SABRE_UP = g(`
.m
.m
.m
.m
fm
S.`);

/** The cut coming down. */
export const SABRE_CUT = g(`
SSf....
...m...
....m..
.....mm`);

/** Carbine to the shoulder; the muzzle is at (8, 0). */
export const CARBINE = g('wwfmmmmmm');

// --- artillery ------------------------------------------------------------------------------------------------

/** A field gun: wheel, bronze barrel, trail to the ground; the muzzle is at (20, 3). */
export const GUN = g(`
......................
......wwwww...........
.....w..w..w..........
....w.ccccccccccccccc.
...kwcccccccccccccccc.
..kkwwwwwkwwww........
.kk.w...w...w.........
kk...w..w..w..........
k.....wwwww...........`);

// --- effects --------------------------------------------------------------------------------------------------

export const FLASH = g(`
.y.
yoy
.y.`);

export const SPARK = g(`
y.y
.y.
y.y`);

export const SMOKE_SMALL = g(`
.gg.
gggG
.GG.`);

export const SMOKE_LARGE = g(`
..gggg..
.gggggG.
ggggggGG
.gGGGGG.
..GGG...`);

export const SMOKE_GUN = g(`
...gggg...
.gggggggG.
gggggggggG
ggggggGGGG
.gGGGGGGG.
...GGGG...`);

// --- ground ---------------------------------------------------------------------------------------------------

export const WIDTH = 48;
export const HEIGHT = 32;
/** The first row of ground: figures stand on the row above it. */
export const GROUND_TOP = 27;

const across = (pattern: string): string => pattern.repeat(Math.ceil(WIDTH / pattern.length)).slice(0, WIDTH);

export const GRASS = [
  across('llLlllllllLlllll'),
  across('lllllLllllllllLl'),
  across('LlllllllLlllllll'),
  across('lllLllllllllLlll'),
  across('llllllLlllllllll'),
];

/** A tree in the back of the scene: canopy over a trunk down to the ground. */
export const TREE = g(`
..EEEE..
.EEEEEE.
EEEEEEEE
EEEEEEEE
.EEEEEE.
..EEEE..
...tt...` + '\n...tt...'.repeat(GROUND_TOP - 7));

/** A trunk close in front of the scene, and leaves hanging into it from above. */
export const TRUNK = Array.from({ length: GROUND_TOP + 1 }, () => 'Ttt');
export const LEAVES = [across('eeeEeeeeeeEeeeee'), across('e.eEee.eee.Eee.e'), across('..e...e...e..e..')];

export const ROCK = g(`
.rrr.
rrrRR
rRRRR`);

export const PEBBLES = g(`
r..R
.r..`);
