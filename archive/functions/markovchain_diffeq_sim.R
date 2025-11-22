markovchain_diffeq_sim <- function(init, rate_func, stat, time) {

  # init internal time
  t <- 0

  # before entering loop, set up list to track casualties per side
  # where for each side, we want to save: the initial size, the current size, morale
  # morale is parsed as the second value in the stat string, and is multiplied by 10 to get a starting morale value
  casualties <- list(
    init = as.list(init),
    losses = as.list(setNames(rep(0, length(init)), names(init))),
    morale = as.list(sapply(stat, \(s) {
      parts <- unlist(strsplit(s, "/"))
      as.numeric(parts[2]) * 10
    }))
  )

  # create tbl to track state
  # t = time
  # init = starting size of sides
  output <- as.data.frame(as.list(c("time" = t, init, casualties$morale)))
  
  # loop across
  while (t < time) {

    # calculate casualty rates for each side
    coef <- sapply(stat, parse_stat_string)

    # returns casualties inflicted on each side
    # A.B means casualties inflicted by B on A
    full_casualty <- sapply(rate_func, \(f) {f(init, coef)})
    
    # get amount of casualties
    casualty <- abs(full_casualty)

    # get direction (should be negative unless reinforcements are involved)
    # -1 = losses, +1 = gains
    dir <- sign(full_casualty)

    # `rexp` introduces the randomness and continuous-time aspect to the Markov chain by sampling the time to the next event from an exponential distribution, where the rate of that distribution is determined by the current casualty rates calculated from the Lanchester equations -- allowing for the simulation to model the inherently unpredictable nature of combat
    clocks <- suppressWarnings(sapply(casualty,
                                      \(r) {rexp(1, rate = r)}))
    
    # clean invalid output
    clocks <- ifelse(is.na(clocks), Inf, clocks)
    
    # increment time by fastest occurrence
    t <- t + min(clocks)

    # few steps:
    #  1) figure out which side had the fastest time to trigger an event
    #  2) tabulate to get a vector of same length as init with 1 on side it occurred
    #  3) multiply the dir by that side to get directionality
    #  4) add to init vector, killing 1st man from fastest side
    init <- init + dir * tabulate(which.min(clocks), nbins = length(init))

    # update casualties taken this step for each side
    # map across casualties$losses and add the absolute value of dir * tabulate(which.min(clocks), nbins = length(init))
    casualties$losses <- Map(\(prior, new) prior + abs(new), casualties$losses, dir * tabulate(which.min(clocks), nbins = length(init)))

    # update coefficients for next loop iteration based on casualties taken and initial size
    # passing time - t for delta_t to get time left in step, this way as delta_t approaches 0, the faster casualty rules have more impact (since formula is casualties / (1 + delta_t))
    casualties <- update_morale_losses(casualties = casualties, delta_t = time - t)

    # make new stat string based on updated morale
    # going to only get stat strings for closest morale value (to calculate coef), but will keep raw morale value for internal calculations
    # that way we can have a more granular morale effect on the simulation, but still use the discrete stat blocks for coef calculations
    # therefore the unit is only penalized when it crosses a morale threshold, giving some leeway for recovery/fluctuation/etc
    stat <- get_closest_stat_string(original_stat = stat, new_morale = unlist(casualties$morale))

    # bind state to df
    output <- rbind(output, as.list(c("time" = t, init, casualties$morale)))

    # if either side has 0 men left, break - TODO - update to break on morale threshold too
    if (any(init == 0) || any(casualties$morale < 10)) break else next
  }

  return(list(df = output, final_casualties = casualties))
}