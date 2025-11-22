get_closest_stat_string <- function(original_stat, new_morale) {

  # vectorized over sides

  # split original stat string into components
  parts <- lapply(original_stat, \(stat) unlist(strsplit(stat, "/")))

  # find closest floored morale value in 1-10 scale (multiply by 10 to match internal morale scale)
  morale_options <- seq(1, 10) * 10
  
  # map names of parts to closest morale value (2nd part of stat string)
  # was going to do floor of morale value, but it's a harsh penalty to drop down a full morale level as soon as you lose 1 person
  # especially considering each stat block starts at a multiple of 10
  closest_morale <- sapply(new_morale, \(m) {
    morale_diffs <- abs(morale_options - m) # closest morale option regardless of direction
    morale_options[which.min(abs(morale_diffs))]
  })

  # reconstruct stat string with closest morale value
  new_stat <- mapply(\(parts, morale) {
    parts[2] <- as.character(morale/10) # convert back to 1-10 scale for stat string
    paste(parts, collapse = "/")
  }, parts, closest_morale, SIMPLIFY = TRUE)

  # return new stat strings
  return(new_stat)

}