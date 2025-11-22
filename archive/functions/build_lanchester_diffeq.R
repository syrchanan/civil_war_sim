build_lanchester_diffeq <- function(init = c("B" = 10, "R" = 10),
                               type = c("B" = "sq", "R" = "sq"),
                               stat = c("B" = "1/1/-2/1", "R" = "1/1/-2/1")) {
  
  # check args
  stopifnot(
    "Only two sides are needed" = length(init) == 2,
    "Each side must have `coef` and `type`" = length(init) == length(type) && length(type) == length(stat),
    "All sides must be named the same across all args" = all(sort(names(init)) == sort(names(type))) && all(sort(names(init)) == sort(names(stat))),
    "All inputs must be atomic named vectors" = all(sapply(list(init, type, stat), is.atomic)),
    "All inputs must be named" = all(sapply(list(init, type, stat), \(x) !is.null(names(x)) && all(names(x) != ""))),
    "All `init` values must be non-negative" = all(init >= 0),
    "All `type` values must be either 'ln' or 'sq'" = all(type %in% c("ln", "sq")),
    "All `stat` values must be valid stat strings" = all(sapply(stat, is_valid_stat_string)),
    "At least one side must have a non-zero initial size" = any(init > 0)
  )

  # make coefficients from stat strings
  sapply(stat, parse_stat_string) -> coef
  
  # assign crossed names
  sapply(names(init), \(side) names(init)[names(init) != side]) -> oppo
  
  # ln and sq calc 
  lanch <- function(side, type, oppo) {
    # get metadata
    law <- type[side]
    rate <- coef[oppo[side]]

    # if linear law, then return that diff eq func
    if (law == "ln") {
      return(
        function(state, coef) {
          -coef[oppo[side]] * state[side] * state[oppo[side]]
        } 
      )
    
    # if square law, then return that diff eq func
    } else if (law == "sq"){
      return(
        function(state, coef) {
          -coef[oppo[side]] * state[oppo[side]]
        }
      )

    # otherwise error out
    } else {
      stop("Unrecognized attrition type ", law) 
    }
  } 

  # return initial state to map across, rate funcs, and stats for later updating
  output <- list(
    "state" = init,
    "rate_func" = sapply(names(init), type = type, oppo = oppo, lanch),
    "stat" = stat
  )

  # set name per rate func
  names(output$rate_func) <- names(init)

  return( output )
}