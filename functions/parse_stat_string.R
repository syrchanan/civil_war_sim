parse_stat_string <- function(stat, return_coef = T) {

  # Input validation: Ensure the stat string is valid.
  if (!is_valid_stat_string(stat)) {
    stop("Invalid stat string format. Expected format: 'xp/morale/weapon/melee' with valid ranges.")
  }

  vec <- as.numeric( strsplit(stat, "/")[[1]] )

  if (!return_coef) {
    return( vec )
  } else {
    return( get_combat_efficiency(vec[1], vec[2], vec[3], vec[4]) )
  }

}