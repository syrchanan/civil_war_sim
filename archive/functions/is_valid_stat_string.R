is_valid_stat_string <- function(stat_string) {
  # Check if the input is a character string
  if (!is.character(stat_string) || length(stat_string) != 1) {
    return(FALSE)
  }
  
  # Split the string by '/'
  parts <- unlist(strsplit(stat_string, "/"))
  
  # Check if there are exactly four parts
  if (length(parts) != 4) {
    return(FALSE)
  }
  
  # Convert parts to numeric and check for NA values
  numeric_parts <- as.numeric(parts)
  if (any(is.na(numeric_parts))) {
    return(FALSE)
  }

  # Check all are integers
  if (any(numeric_parts != floor(numeric_parts))) {
    return(FALSE)
  }
  
  # Check the specific conditions for each part
  # 1 => 1-10
  # 2 => 1-10
  # 3 => -2 to 2
  # 4 => 0 or 1
  if (!(numeric_parts[1] >= 1 && numeric_parts[1] <= 10)) {
    return(FALSE)
  } else if (!(numeric_parts[2] >= 1 && numeric_parts[2] <= 10)) {
    return(FALSE)
  } else if (!(numeric_parts[3] >= -2 && numeric_parts[3] <= 2)) {
    return(FALSE)
  } else if (!(numeric_parts[4] == 0 || numeric_parts[4] == 1)) {
    return(FALSE)
  }
  
  # If all checks passed, return TRUE
  return(TRUE)
}