markovchain_diffeq_sim <- function(init, rate_func, stat, time) {

  # init internal time
  t <- 0
  
  # create tbl to track state
  # t = time
  # init = starting size of sides
  output <- as.data.frame(as.list(c("time" = t, init)))

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

  # causalty logic has 4 rules
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

    # bind state to df
    output <- rbind(output, as.list(c("time" = t, init)))

    # update casualties taken this step for each side
    casualties$losses <- mapply(\(prev, curr, loss) loss + max(0, prev - curr), casualties$init, init, casualties$losses, SIMPLIFY = FALSE)

    # update coefficients for next loop iteration based on casualties taken and initial size
    update_morale_losses(stat = stat, casualties = casualties, delta_t = t)

    # if either side has 0 men left, break - TODO - update to break on morale threshold too
    if (any(init == 0)) break else next
  }

  output
}