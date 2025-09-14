update_morale_losses <- function(casualties, delta_t) {
  # Casualty-based Morale Logic has 4 rules
  # ▪ Rule A: Casualties Sustained (Morale Falls):
  #     • Calculate loss_percentage = B_casualties_taken_this_step / previous_B_soldiers. (Handle division by zero if previous_B_soldiers is 0).
  #     • morale_change_for_B = morale_change_for_B - (loss_percentage * Morale_Loss_Constant_1)
  #     • (Rationale: A unit taking losses will experience a drop in morale. The previous_B_soldiers provides a stable baseline for this percentage calculation.)
  # ▪ Rule B: Casualties Inflicted (Morale Rises):
  #     • Calculate infliction_percentage = R_casualties_taken_this_step / previous_R_soldiers. (Handle division by zero if previous_R_soldiers is 0).
  #     • morale_change_for_B = morale_change_for_B + (infliction_percentage * Morale_Gain_Constant_1)
  #     • (Rationale: Successfully inflicting casualties boosts morale, reflecting "High-spirited, eager" or "Patriotic exuberance!".)
  # ▪ Rule C: Faster Casualties Sustained (More Morale Falls):
  #     • Calculate casualties_per_unit_time_taken = B_casualties_taken_this_step / delta_t. (Handle delta_t being zero or extremely small to avoid Inf or NaN; you might cap this value or add a small epsilon to delta_t).
  #     • morale_change_for_B = morale_change_for_B - (casualties_per_unit_time_taken * Morale_Loss_Constant_2)
  #     • (Rationale: Rapid, heavy losses are more demoralizing than slow attrition, even for the same total casualty count. This reflects the "shaken, shell-shocked" state.)
  # ▪ Rule D: Faster Casualties Inflicted (Faster Morale Rises):
  #     • Calculate casualties_per_unit_time_inflicted = R_casualties_taken_this_step / delta_t. (Handle delta_t being zero or extremely small).
  #     • morale_change_for_B = morale_change_for_B + (casualties_per_unit_time_inflicted * Morale_Gain_Constant_2)
  #     • (Rationale: A rapid, successful advance or defense significantly boosts a unit's spirit.)

  # Constants for morale adjustments
  # In general, the constants for morale loss should be higher than those for morale gain to reflect the psychological impact of losses versus gains in combat situations.
  # Constant 2 weights heavier towards the end of the time step, so should be lower than Constant 1
  Morale_Loss_Constant_1 <- 0.00007 # Rule A: Casualties Sustained
  Morale_Gain_Constant_1 <- 0.00005 # Rule B: Casualties Inflicted
  Morale_Loss_Constant_2 <- 0.0000040 # Rule C: Faster Casualties Sustained
  Morale_Gain_Constant_2 <- 0.0000040 # Rule D: Faster Casualties Inflicted

  # Initialize morale changes for each side
  morale_changes <- setNames(
    rep(0, length(casualties$init)),
    names(casualties$init)
  )

  # Loop through each side to calculate morale changes
  for (side in names(casualties$init)) {
    # Identify the opposing side
    opposing_side <- setdiff(names(casualties$init), side)

    # Get casualties inflicted and taken
    casualties_inflicted <- casualties$losses[[opposing_side]]
    casualties_taken <- casualties$losses[[side]]

    # Rule A: Casualties Sustained (More Morale Falls)
    infliction_percentage <- casualties_taken / casualties$init[[side]]
    morale_changes[side] <- morale_changes[side] -
      (infliction_percentage * Morale_Loss_Constant_1)

    # Rule B: Casualties Inflicted (Morale Rises)
    infliction_percentage <- casualties_inflicted /
      casualties$init[[opposing_side]]
    morale_changes[side] <- morale_changes[side] +
      (infliction_percentage * Morale_Gain_Constant_1)

    # Rule C: Faster Casualties Sustained (More Morale Falls)
    casualties_per_unit_time_taken <- casualties_taken / (1 + delta_t)
    morale_changes[side] <- morale_changes[side] -
      (casualties_per_unit_time_taken * Morale_Loss_Constant_2)

    # Rule D: Faster Casualties Inflicted (Faster Morale Rises)
    casualties_per_unit_time_inflicted <- casualties_inflicted / (1 + delta_t)
    morale_changes[side] <- morale_changes[side] +
      (casualties_per_unit_time_inflicted * Morale_Gain_Constant_2)
  }

  # Update morale values in the casualties list and return
  for (side in names(casualties$morale)) {
    new_morale <- casualties$morale[[side]] + morale_changes[[side]]
    # Ensure morale stays within bounds [10, 100] (1-10 scale from rules, multiplied by 10)
    casualties$morale[[side]] <- max(10, min(100, new_morale))
  }

  return(casualties)
}
