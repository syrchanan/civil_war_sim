build_lanchester_diffeq <- function(init = c("B" = 10, "R" = 10),
                               coef = c("B" = 1, "R" = 1),
                               type = c("B" = "sq", "R" = "sq")) {
  
  # check args
  stopifnot(
    "Only two sides are needed" = length(init) == 2,
    "Each side must have `coef` and `type`" = length(init) == length(coef) && length(init) == length(type),
    "All sides must be named the same across all args" = all(sort(names(init)) == sort(names(coef))) && all(sort(names(init)) == sort(names(type))),
    "All inputs must be atomic named vectors" = all(sapply(list(init, coef, type), is.atomic))
  )
  
  # assign crossed names
  sapply(names(init), function(side) names(init)[names(init) != side]) -> oppo
  
  # ln and sq calc 
  lanch <- function(side, type, oppo) {
    # get metadata
    law <- type[side]
    rate <- coef[oppo[side]]

    # if linear law, then return that diff eq func
    if (law == "ln") {
      return(function(state) -rate * state[side] * state[oppo[side]])
    
    # if square law, then return that diff eq func
    } else if (law == "sq"){
      return(function(state) -rate * state[oppo[side]])

    # otherwise error out
    } else {
      stop("Unrecognized attrition type ", law) 
    }
  } 

  # return initial state to map across and rate funcs
  output <- list(
    "state" = init,
    "rate_func" = sapply(names(init), type = type, oppo = oppo, lanch)
  )

  # set name per rate func
  names(output$rate_func) <- names(init)

  return( output )
}