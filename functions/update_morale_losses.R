update_morale_losses <- function(stat, casualties, delta_t) {

  # Parse stat strings into numeric coefficients, with names assigned based on (xp, morale, weapon, melee)
  sapply(stat, parse_stat_string, F) -> stat_parsed 

  # Constants for morale adjustments
  Morale_Loss_Constant_1 <- 0.05  # Rule A: Casualties Sustained
  Morale_Gain_Constant_1 <- 0.03  # Rule B: Casualties Inflicted
  Morale_Loss_Constant_2 <- 0.02  # Rule C: Faster Casualties Sustained
  Morale_Gain_Constant_2 <- 0.01  # Rule D: Faster Casualties Inflicted
  
  # Initialize morale changes for each side
  morale_changes <- setNames(rep(0, length(stat)), names(stat))
  
  # Loop through each side to calculate morale changes
  for (side in names(stat)) {
    # Identify the opposing side
    opposing_side <- setdiff(names(stat), side)
    
    # Get casualties inflicted and taken
    casualties_inflicted <- casualties$losses[[opposing_side]]
    casualties_taken <- casualties$losses[[side]]
    
    # Rule A: Casualties Sustained (More Morale Falls)
    if (initial_size > 0) {
      infliction_percentage <- casualties_taken / casualties$init[[side]]
      morale_changes[side] <- morale_changes[side] - (infliction_percentage * Morale_Loss_Constant_1)
    }
    
    # Rule B: Casualties Inflicted (Morale Rises)
    if (initial_size > 0) {
      infliction_percentage <- casualties_inflicted / casualties$init[[opposing_side]]
      morale_changes[side] <- morale_changes[side] + (infliction_percentage * Morale_Gain_Constant_1)
    }
    
    # Rule C: Faster Casualties Sustained (More Morale Falls)
    if (delta_t > 0) {
      casualties_per_unit_time_taken <- casualties_taken * (1 + delta_t)
      morale_changes[side] <- morale_changes[side] - (casualties_per_unit_time_taken * Morale_Loss_Constant_2)
    }
    
    # Rule D: Faster Casualties Inflicted (Faster Morale Rises)
    if (delta_t > 0) {
      casualties_per_unit_time_inflicted <- casualties_inflicted * (1 + delta_t)
      morale_changes[side] <- morale_changes[side] + (casualties_per_unit_time_inflicted * Morale_Gain_Constant_2)
    }
  }

  # Update morale values in the casualties list and return
  for (side in names(casualties$morale)) {
    new_morale <- casualties$morale[[side]] + morale_changes[[side]]
    # Ensure morale stays within bounds [10, 100] (1-10 scale from rules, multiplied by 10)
    casualties$morale[[side]] <- max(10, min(100, new_morale))
  }

  # TODO - function to update stat string based on new morale value (divide by 10 and floor to get back to our 1-10 scale)
    
  return(casualties)

}