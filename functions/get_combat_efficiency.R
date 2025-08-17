get_combat_efficiency <- function(
  stat_xp = NULL,     # Unit's experience (1-10)
  stat_morale = NULL, # Unit's current morale (1-10 or 10-100 granular)
  stat_weapon = NULL, # Unit's weapon tier (-2 to 2)
  stat_melee = NULL,  # 0 for ranged, 1 for melee
  return_table = FALSE # Set to TRUE to return the full lookup table
) {
  # --- Define Parameters for Coefficient Calculation (Constants) ---
  # These parameters are based directly on the "Regiment Combat Coefficient Calculation and Lookup" source.
  
  # 1. Weapon Multipliers (Categorical)
  # Represents the base effectiveness of a regiment's primary weapon.
  weapon_multipliers <- c(
    "-2" = 0.20, # Unarmed or pikemen - very low effectiveness
    "-1" = 0.50, # Smoothbore matchlocks - inferior
    "0" = 1.00,  # Smoothbore muskets - standard/old for new regiments
    "1" = 1.50,  # Rifled muskets - significant improvement
    "2" = 2.50   # Needler rifles - highly advanced, major advantage
  )
  
  # 2. Experience and Morale Boosts (Linear)
  # Incremental improvements based on a unit's training and spirit.
  xp_boost_per_level <- 0.04   # 4% increase in effectiveness per experience level above 1
  morale_boost_per_level <- 0.02 # 2% increase in effectiveness per morale level above 1
  
  # 3. Melee Combat Penalty
  # Melee combat is less effective than aimed fire.
  melee_penalty_factor <- 0.70 # Melee effectiveness is 70% of ranged effectiveness
  
  # --- Calculate Maximum Possible Raw Coefficient for Scaling ---
  # This fixed value ensures the final coefficient is between 0 and 1,
  # where 1 is the highest possible effectiveness ("one shot, one casualty" principle).
  max_weapon_base <- max(weapon_multipliers)
  max_xp_adj <- (10 - 1) * xp_boost_per_level
  max_morale_adj <- (10 - 1) * morale_boost_per_level
  max_possible_raw_coefficient <- max_weapon_base * (1 + max_xp_adj + max_morale_adj)

  # --- Function Logic ---
  # If 'return_table' is TRUE, generate and return the full lookup table.
  if (return_table) {
    # Create the initial expanded grid of all possible stat combinations
    stat_data <- expand.grid(
      stat_morale = 1:10,
      stat_xp = 1:10,
      stat_weapon = -2:2,
      stat_melee = 0:1 # 0 for Ranged, 1 for Melee
    )

    # Calculate the combat coefficient for each row in the stat_data
    full_lookup_table <- stat_data %>%
      dplyr::mutate(
        # Step 1: Get the base effectiveness from the weapon tier
        weapon_base_effectiveness = weapon_multipliers[as.character(stat_weapon)],
        
        # Step 2: Calculate adjustments from Experience and Morale
        xp_adjustment = (stat_xp - 1) * xp_boost_per_level,
        morale_adjustment = (stat_morale - 1) * morale_boost_per_level,
        
        # Step 3: Combine all positive adjustments (weapon, experience, morale)
        adjusted_effectiveness = weapon_base_effectiveness * (1 + xp_adjustment + morale_adjustment),
        
        # Step 4: Apply the melee penalty if the unit is in melee
        raw_combat_coefficient = ifelse(
          stat_melee == 1,
          adjusted_effectiveness * melee_penalty_factor,
          adjusted_effectiveness
        ),
        
        # Step 5: Scale the raw coefficient to be between 0 and 1
        final_combat_coefficient = raw_combat_coefficient / max_possible_raw_coefficient,
        
        # Step 6: Create a unique string identifier for each stat combination
        stat_string = paste(stat_xp, stat_morale, stat_weapon, stat_melee, sep = "/")
      ) %>%
      # Select and reorder columns for the final lookup table
      dplyr::select(stat_string, coef = final_combat_coefficient) %>%
      dplyr::arrange(-coef)

    return(full_lookup_table)

  } else {
    # Default behavior: Calculate and return a single efficiency value
    # Input validation: Ensure all necessary stats are provided for a single calculation.
    if (is.null(stat_morale) || is.null(stat_xp) || is.null(stat_weapon) || is.null(stat_melee)) {
      stop("When `return_table` is FALSE, `stat_xp`, `stat_morale`, `stat_weapon`, and `stat_melee` must be provided to calculate a single efficiency value.")
    }

    # Morale conversion: The dynamic morale system tracks granular morale from 10-100.
    # This must be converted back to the 1-10 scale for coefficient calculation.
    if (stat_morale > 10) {
      stat_morale_1_10 <- round(stat_morale / 10)
    } else {
      stat_morale_1_10 <- stat_morale
    }

    # Input clamping for robustness: Ensures inputs are within expected valid ranges.
    # (This is an enhancement for robustness, inferred from the game's stat ranges).
    stat_morale_1_10 <- max(1, min(10, stat_morale_1_10))
    stat_xp <- max(1, min(10, stat_xp))
    stat_weapon <- max(-2, min(2, stat_weapon))
    stat_melee <- max(0, min(1, stat_melee))

    # Perform the calculations for the single set of stats:
    # Step 1: Get the base effectiveness from the weapon tier
    weapon_base_effectiveness <- weapon_multipliers[as.character(stat_weapon)]
    
    # Step 2: Calculate adjustments from Experience and Morale
    xp_adjustment <- (stat_xp - 1) * xp_boost_per_level
    morale_adjustment <- (stat_morale_1_10 - 1) * morale_boost_per_level
    
    # Step 3: Combine all positive adjustments
    adjusted_effectiveness <- weapon_base_effectiveness * (1 + xp_adjustment + morale_adjustment)
    
    # Step 4: Apply the melee penalty if applicable
    raw_combat_coefficient <- ifelse(
      stat_melee == 1,
      adjusted_effectiveness * melee_penalty_factor,
      adjusted_effectiveness
    )
    
    # Step 5: Scale the raw coefficient to be between 0 and 1
    final_combat_coefficient <- raw_combat_coefficient / max_possible_raw_coefficient

    return(final_combat_coefficient)
  }
}