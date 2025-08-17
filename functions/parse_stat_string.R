parse_stat_string <- function(stat, return_coef = T) {

  vec <- as.numeric( strsplit(stat, "/")[[1]] )

  if (!return_coef) {
    return( vec )
  } else {
    return( get_combat_efficiency(vec[1], vec[2], vec[3], vec[4]) )
  }

}