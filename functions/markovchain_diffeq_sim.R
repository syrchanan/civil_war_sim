markovchain_diffeq_sim <- function(init, rate_func, time) {

  # init internal time
  t <- 0
  
  # create tbl to track state
  # t = time
  # init = starting size of sides
  output <- as.data.frame(as.list(c("time" = t, init)))

  # loop across
  while (t < time) {

    # returns casualties inflicted on each side
    # A.B means casualties inflicted by B on A
    full_casualty <- sapply(rate_func, \(f) {f(init)})
    
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

    # if either side has 0 men left, break
    if (any(init == 0)) break else next
  }

  output
}