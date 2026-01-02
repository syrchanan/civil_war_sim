import { Regiment } from '../units/Regiment';
export declare class Simulation {
    forces: [Regiment, Regiment];
    rate_funcs: [((sizes: number[], coef: number[], idx: number) => number), ((sizes: number[], coef: number[], idx: number) => number)] | null;
    casualties: {
        initial_size: [number, number];
        losses: [number, number];
        morale: [number, number];
    };
    sim_output: Array<{
        time: number;
        size_1: number;
        size_2: number;
        morale_1: number;
        morale_2: number;
    }>;
    /**
     * Simulation constructor
     * @param forces Tuple of two Regiment instances representing opposing forces
     */
    constructor(forces: [Regiment, Regiment]);
    /**
     * String representation of Simulation
     * @returns string String representation
     */
    toString(): string;
    /**
     * Convert Simulation to JSON representation
     * @returns Object JSON representation of the Simulation
     */
    toJSON(): object;
    private static _lanchester_diffeq;
    build_lanch_diffeq(): void;
    private _update_morale_losses;
    run_simulation(time: number): void;
}
//# sourceMappingURL=Simulation.d.ts.map