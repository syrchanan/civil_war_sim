#!/usr/bin/Rscript
# ContTimeLanchesterModel.R
# 2024-01-13
# curtis
# An R script for continuous time Lanchester models

# PACKAGES ---------------------------------------------------------------------

library(dplyr)
library(tidyr)
library(purrr)

# FUNCTIONS --------------------------------------------------------------------

#' Lanchester Attrition Model Setup
#'
#' Prepare inputs to \code{\link{ctmc_deq_sim}} for simulating an engagement
#' according to either linear or square law Lanchester equations
#'
#' This function is effectively limited to only two types of forces (Blue and
#' Red, effectively) and only either linear or square law type attrition.
#'
#' @param init Vector of initial starting force size
#' @param coef Vector of casualty infliction coefficients
#' @param type Vector with entries either \code{"sq"} or \code{"ln"} for
#'             taking linear or square law type attrition
#' @return \code{\link[base]{list}} with entries \code{state} and
#'         \code{transition_func} that are the initial state of the model and
#'         contain the transition function, and thus can be given to
#'         \code{\link{ctmc_deq_sim}}
#' @examples
#' lanchester_deq_gen()
#' lanchester_deq_gen(init = c("B" = 150, "R" = 70),
#'                    coef = c("B" = 7/1000, "R" = 15/1000),
#'                    type = c("B" = "ln", "R" = "sq"))
#' @export
#' @seealso \code{\link{ctmc_deq_sim}}
lanchester_deq_gen <- function(init = c("B" = 10, "R" = 10),
                               coef = c("B" = 1, "R" = 1),
                               type = c("B" = "sq", "R" = "sq")) {
  stopifnot(length(init) == length(coef) && length(init) == length(type))
  stopifnot(all(sort(names(init)) == sort(names(coef))) &&
            all(sort(names(init)) == sort(names(type))))
  stopifnot(length(init) == 2)
  
  counterpart <- sapply(names(init), function(side) names(init)[
    names(init) != side])
  names(counterpart) <- names(init)
  out_list <- list(
    "state" = init,
    "transition_func" = sapply(names(init), FUN = function(side) {
      tp <- type[side]
      cf <- coef[counterpart[side]]
      if (tp == "ln") {
        return(function(s) -cf * s[side] * s[counterpart[side]])
      } else if (tp == "sq"){
        return(function(s) -cf * s[counterpart[side]])
      } else {
        stop("Unrecognized attrition type ", tp)
      }
  }))
  names(out_list$transition_func) <- names(init)

  out_list
}

#' Continuous Time Markov Chain Differential Equation Transition Simulation
#'
#' Simulate a single continuous time Markov chain realization corresponding to a
#' differential equation describing transition rates
#'
#' The magnitude of values returned by \code{transition_func} entries determines
#' transition rate while the sign determines the direction the chain moves in.
#'
#' @param state Initial state of the chain, a vector
#' @param transition_func A vector of functions, each of which takes a vector
#'                        similar to the state vector, and returns univariate
#'                        numeric results each
#' @param time The time to run the chain
#' @return A \code{\link[base]{data.frame}} with an additional column \code{t}
#'         containing transition times and all other columns corresponding to
#'         the entries of \code{state}
#' @examples
#' ctmc_deq_sim(c("a" = 100), c("a" = function(s) -s["a"]), 10)
#' sim_setup <- lanchester_deq_gen(init = c("B" = 150, "R" = 70),
#'                                 coef = c("B" = 7/1000, "R" = 15/1000),
#'                                 type = c("B" = "ln", "R" = "sq"))
#' with(sim_setup, ctmc_deq_sim(state, transition_func, 1))
#' @export
#' @seealso \code{\link{lanchester_deq_gen}}
ctmc_deq_sim <- function(state, transition_func, time) {
  t <- 0
  out_df <- as.data.frame(as.list(c("t" = t, state)))

  while (t < time) {
    fval <- sapply(transition_func, FUN = function(f) {f(state)})
    rates <- abs(fval)
    dir <- sign(fval)
    clocks <- suppressWarnings(sapply(rates,
                                      function(r) {rexp(1, rate = r)}))
    clocks <- ifelse(is.na(clocks), Inf, clocks)
    t <- t + min(clocks)
    state <- state + dir * tabulate(which.min(clocks), nbins = length(state))
    out_df <- rbind(out_df, as.list(c("t" = t, state)))
  }

  out_df
}

#' Linked Continuous Time Markov Chain Differential Equation Transition
#' Simulation
#'
#' Simulate a single continuous time Markov chain realization corresponding to a
#' differential equation that switches to different chains based on time spent
#' in a chain
#'
#' Note that the list in \code{stage_list} may describe the initial state of
#' Markov chains, but only the first one is used; the rest are ignored, with the
#' Markov chain using the most recent state of the chain.
#'
#' @param stage_list List of lists each in the format returned by
#'                   \code{\link{lanchester_deg_gen}}
#' @param time Vector containing time to remain in each stage
#' @return A \code{\link[base]{data.frame}} with an additional column \code{t}
#'         containing transition times and all other columns corresponding to
#'         the entries of \code{state}
#' @examples
#' ambush_setup <- lanchester_deq_gen(init = c("B" = 150, "R" = 70),
#'                                    coef = c("B" = 7/1000, "R" = 15/1000),
#'                                    type = c("B" = "ln", "R" = "sq"))
#' normal_setup <- lanchester_deq_gen(init = c("B" = 150, "R" = 70),
#'                                    coef = c("B" = 15/1000, "R" = 7/1000),
#'                                    type = c("B" = "sq", "R" = "sq"))
#' combat_time <- 7
#' reorg_time <- min(rexp(1, 1/(1/10)), combat_time)
#' linked_ctmc_deq_sim(list(ambush_setup, normal_setup), c(reorg_time,
#'                                                         combat_time - reorg_time))
#' @export
#' @seealso \code{\link{lanchester_deq_gen}}, \code{\link{ctmc_deq_sim}}
linked_ctmc_deq_sim <- function(stage_list, time) {
  stopifnot(length(stage_list) == length(time))
  out_df <- with(stage_list[[1]],
    ctmc_deq_sim(state = state,
                 transition_func = transition_func,
                 time = time[[1]]))
  if (length(stage_list) == 1) {
    return(out_df)
  }
  
  for (i in 2:length(stage_list)) {
    model <- stage_list[[i]]
    out_df <- out_df[1:(nrow(out_df) - 1),]
    last_state <- as.numeric(tail(out_df, 1))
    names(last_state) <- names(out_df)
    last_state <- last_state[names(last_state) != "t"]
    model$state <- last_state
    next_df <- with(model,
      ctmc_deq_sim(state = state,
                   transition_func = transition_func,
                   time = time[[i]])
    )
    next_df <- next_df[2:nrow(next_df),]
    next_df$t <- next_df$t + tail(out_df$t, 1)
    out_df <- rbind(out_df, next_df)
  }
  rownames(out_df) <- NULL

  out_df
}

#' Simple Threshold Retreat Function Generation
#'
#' Creates a list of closures that determine retreat based on whether the force
#' size drops to below some specified level
#'
#' This function is intended to be used with \code{\link{retreat_detection}},
#' generating one of the inputs the function needs. It uses a simple retreat
#' rule where the force retreats if its force level drops below a certain
#' number. This can be phrased either as a proportion of the initial force size
#' or in an absolute term.
#'
#' @param retreat_level If \code{init} is not set, this should be the minimum
#'                      force level at which a retreat would not occur; if
#'                      \code{init} is not \code{NULL}, then this is the minimum
#'                      proportion of initial force level at which retreat would
#'                      not occur
#' @param init Initial force level
#' @return A \code{\link[base]{list}} of functions each of which accept a vector
#'         as input with named entries corresponding to forces and return a
#'         boolean for whether the force retreats
#' @examples
#' simple_threshold_retreat_func_gen(c("B" = 100, "R" = 50))
#' simple_threshold_retreat_func_gen(c("B" = 0.7, "R" = 0.8),
#'                                   init = c(150, 70))
#' @export
#' @seealso \code{\link{retreat_detection}}
simple_threshold_retreat_func_gen <- function(retreat_level, init = NULL) {
  fnames <- names(retreat_level)
  stopifnot(!is.null(names(retreat_level)))

  if (!is.null(init)) {
    stopifnot(all(sort(names(retreat_level)) == sort(names(init))))
    init <- init[names(retreat_level)]
    retreat_level <- retreat_level * init
  }

  res <- sapply(fnames, FUN = function(nm) {
    function(s) s[nm] < retreat_level[nm]
  })
  names(res) <- fnames

  res
}

#' Detect a Retreating Force
#'
#' Detect a force in retreat, along with state information at the time of
#' retreat
#'
#' The model for retreats in this case is very simple: if in a row retreat rules
#' are met, the force retreats. The history of the process other than its
#' current state is not considered. Also, retreat is immediate, and thus no time
#' is taken for the force to organize a retreat.
#'
#' @param engagement_df A \code{\link[base]{data.frame}} like that returned by
#'                      \code{\link{ctmc_deq_sim}} containing the attrition of
#'                      forces
#' @param retreat_threshold A vector of functions each of which accept as input
#'                          all columns of \code{engagement_df} as a vector and
#'                          returns \code{TRUE} or \code{FALSE}
#' @return A \code{\link[base]{list}} with elements corresponding to each
#'         column of \code{engagement_df} and an additional element,
#'         \code{retreat}, that is either \code{NA} or the name of the column
#'         where a retreat was detected; all entries are either the last entry
#'         or the entry at the time of retreat, and the \code{retreat} entry of
#'         the list is \code{NA} if no one retreated
#' @examples
#' init <- c("B" = 150, "R" = 70)
#' ambush_setup <- lanchester_deq_gen(init = init,
#'                                    coef = c("B" = 7/1000, "R" = 15/1000),
#'                                    type = c("B" = "ln", "R" = "sq"))
#' normal_setup <- lanchester_deq_gen(init = init,
#'                                    coef = c("B" = 15/1000, "R" = 7/1000),
#'                                    type = c("B" = "sq", "R" = "sq"))
#' combat_time <- 7
#' reorg_time <- min(rexp(1, 1/(1/10)), combat_time)
#' retreat_rules <- simple_threshold_retreat_func_gen(c("B" = .7, "R" = .8),
#'                                                    init = init)
#' attrit <- linked_ctmc_deq_sim(list(ambush_setup, normal_setup), c(reorg_time,
#'                                                                   combat_time - reorg_time))
#' retreat_detection(attrit, retreat_rules)
#' @export
#' @seealso \code{\link{ctmc_deq_sim}}, \code{\link{linked_ctmc_deq_sim}},
#'          \code{\link{simple_threshold_retreat_func_gen}}
retreat_detection <- function(engagement_df, retreat_threshold) {
  fnames <- sort(names(engagement_df)[2:length(engagement_df)])
  stopifnot(all(fnames == sort(names(retreat_threshold))))

  retreat_bool <- lapply(fnames, FUN = function(nm) {
    test_fun <- retreat_threshold[[nm]]
    sapply(1:nrow(engagement_df), FUN = function(i) {
      row <- as.list(engagement_df[i,])
      storage.mode(row) <- "double"
      test_fun(row)
  })})
  names(retreat_bool) <- fnames
  retreat_idx <- sapply(retreat_bool, FUN = function(rb) {
    suppressWarnings(min(which(rb)))
  })
  names(retreat_idx) <- fnames
  if (all(is.infinite(retreat_idx))) {
    retreat_side <- NA
    retreat_row <- nrow(engagement_df)
  } else {
    retreat_side <- names(which(retreat_idx == min(retreat_idx)))
    retreat_row <- min(retreat_idx)
  }
  c(as.list(engagement_df[retreat_row,]), "retreat" = retreat_side)
}

#' Monte Carlo Study of Lanchester Model with Retreating
#'
#' Performs Monte Carlo simulation studies for combat results for the continuous
#' time Lanchester models
#'
#' This function merely makes multiple runs of a Lanchester continuous time
#' stochastic combat simulation with retreating rules and collects the results
#' in a \code{\link[base]{data.frame}}.
#'
#' @param time Either a vector of times to switch engagement stage or a function
#'             that returns such a vector
#' @param replicates Number of times to repeat engagements
#' @inheritParams linked_ctmc_deq_sim
#' @inheritParams retreat_detection
#' @return A \code{\llink[base]{data.frame}} with columns resembling the output
#'         of \code{\link{retreat_detection}}
#' @examples
#' init <- c("B" = 150, "R" = 70)
#' ambush_setup <- lanchester_deq_gen(init = init,
#'                                    coef = c("B" = 7/1000, "R" = 15/1000),
#'                                    type = c("B" = "ln", "R" = "sq"))
#' normal_setup <- lanchester_deq_gen(init = init,
#'                                    coef = c("B" = 15/1000, "R" = 7/1000),
#'                                    type = c("B" = "sq", "R" = "sq"))
#' retreat_rules <- simple_threshold_retreat_func_gen(c("B" = .7, "R" = .8),
#'                                                    init = init)
#' combat_time <- 7
#' time_func <- function() {
#'   reorg_time <- min(rexp(1/(1/10)), combat_time)
#'   c(reorg_time, combat_time - reorg_time)
#' }
#' stage_list <- list(ambush_setup, normal_setup)
#' lanchester_retreat_mc(stage_list, time_func, retreat_rules, replicate = 100)
lanchester_retreat_mc <- function(stage_list, time, retreat_threshold,
                                  replicates = 1000) {
  outputs <- lapply(1:replicates, function(throwaway) {
    if (is.function(time)) {
      time_vec <- time()
    } else {
      time_vec <- time
    }
    attrit <- linked_ctmc_deq_sim(stage_list, time_vec)
    retreat_detection(attrit, retreat_threshold)
  }) 
  Reduce(rbind, lapply(outputs, as.data.frame))
}

# EXECUTABLE SCRIPT MAIN FUNCTIONALITY -----------------------------------------

main <- function(foo, bar = 0, baz = FALSE) {
  replicates <- 100
  no_ambush_attrit_coef <- c("B" = 15/1000, "R" = 7/1000)
  ambush_attrit_coef <- rbind(
    "B" = c("B" = 30/1000, "R" = 3/1000),
    "R" = c("B" = 7/1000, "R" = 15/1000)
  )
  arty_attrit_coef <- c("B" = 15/10, "R" = 10/10)
  mean_reorg_time <- 0.5
  combat_time <- 7
  bombard_time <- 1
  retreat_ratios <- rbind(
    "full" = c("B" = 0.7, "R" = 0.8),
    "weak" = c("B" = 0.9, "R" = 0.95)
  )
  arty_unit_size <- c("B" = 10, "R" = 20)
  troop_unit_size <- c("B" = 150, "R" = 70)
  stack_limit <- 2
  arty_min_size <- c("B" = 2, "R" = 4)
  arty_max_size <- stack_limit * arty_unit_size
  arty_step <- 2
  troop_min_size <- c("B" = 20, "R" = 10)
  troop_max_size <- stack_limit * troop_unit_size
  troop_step <- 10

  arty_table <- bind_rows(
    expand_grid(
      "shooter" = "R",
      "shooter_size" = seq(arty_min_size["R"], arty_max_size["R"], arty_step),
      "target_size" = seq(troop_min_size["B"], troop_max_size["B"], troop_step)
    ),
    expand_grid(
      "shooter" = "B",
      "shooter_size" = seq(arty_min_size["B"], arty_max_size["B"], arty_step),
      "target_size" = seq(troop_min_size["R"], troop_max_size["R"], troop_step)
    )
  )

  troop_table <- bind_rows(
    expand_grid(
      "attacker" = "BR",
      "ambush" = FALSE,
      "B_size" = seq(troop_min_size["B"], troop_max_size["B"], troop_step),
      "R_size" = seq(troop_min_size["R"], troop_max_size["R"], troop_step),
    ),
    expand_grid(
      "attacker" = c("B", "R"),
      ambush = TRUE,
      "B_size" = seq(troop_min_size["B"], troop_max_size["B"], troop_step),
      "R_size" = seq(troop_min_size["R"], troop_max_size["R"], troop_step),
    )
  )

  time_func <- function() {
    reorg_time <- min(rexp(1, rate = 1/mean_reorg_time), combat_time)
    c(reorg_time, combat_time - reorg_time)
  }

  arty_sims <- mutate(arty_table,
      engagement_setup = pmap(arty_table, function(shooter, shooter_size,
                                                   target_size) {
        target <- ifelse(shooter == "B", "R", "B")
        name_vec <- c(shooter, target)
        init <- c(shooter_size, target_size)
        coef <- c(arty_attrit_coef[shooter], 0)
        type <- c("ln", "ln")
        names(init) <- name_vec
        names(coef) <- name_vec
        names(type) <- name_vec
        list(lanchester_deq_gen(init = init, coef = coef, type = type))
      })) %>%
    mutate(retreat = pmap(arty_table, function(shooter, shooter_size,
                                               target_size) {
        target <- ifelse(shooter == "B", "R", "B")
        name_vec <- c(shooter, target)
        init <- c(shooter_size, target_size)
        names(init) <- name_vec
        retreat_type <- ifelse(target_size < (retreat_ratios["full",] * troop_unit_size)[target],
                               "weak", "full")
        retreat_level <- retreat_ratios[retreat_type,]
        simple_threshold_retreat_func_gen(retreat_level = retreat_level,
                                          init = init)
      })) %>%
    mutate(battle_outcome = map2(engagement_setup, retreat,
                                 ~ lanchester_retreat_mc(stage_list = .x,
                                                         retreat_threshold = .y,
                                                         time = bombard_time,
                                                         replicates = replicates))) %>%
    select(-c(engagement_setup, retreat)) %>%
    unnest(battle_outcome) %>%
    replace_na(list(retreat = "NR"))

  troop_sims <- mutate(troop_table,
      engagement_setup = pmap(troop_table, function(attacker, ambush, B_size, R_size) {
        init <- c("B" = B_size, "R" = R_size)
        if (ambush) {
          target <- ifelse(attacker == "B", "R", "B")
          coef <- ambush_attrit_coef[attacker, ]
          type <- c("ln", "sq")
          names(type) <- c(target, attacker)
          engagement_setup_list <- list(lanchester_deq_gen(init = init,
                                                           coef = coef,
                                                           type = type))
        } else {
          engagement_setup_list <- list()
        }
        coef <- no_ambush_attrit_coef
        type <- c("B" = "sq", "R" = "sq")
        append(engagement_setup_list,
               list(lanchester_deq_gen(init = init, coef = coef, type = type)))
      })) %>%
    mutate(retreat = pmap(troop_table,
      function(attacker, ambush, B_size, R_size) {
        init <- c("B" = B_size, "R" = R_size)
        retreat_type <- ifelse(init < (retreat_ratios["full",] * troop_unit_size),
                               "weak", "full")
        retreat_level <- c("B" = retreat_ratios[retreat_type["B"], "B"],
                           "R" = retreat_ratios[retreat_type["R"], "R"])
        simple_threshold_retreat_func_gen(retreat_level = retreat_level,
                                          init = init)
    }))
  troop_sims <- mutate(troop_sims,
                       battle_outcome = pmap(troop_sims, function(attacker, ambush, B_size, R_size, engagement_setup, retreat) {
      if (ambush) {
        time <- time_func
      } else {
        time <- combat_time
      }
      lanchester_retreat_mc(stage_list = engagement_setup,
                            retreat_threshold = retreat,
                            time = time,
                            replicates = replicates)
    })) %>%
    select(-c(engagement_setup, retreat)) %>%
    unnest(battle_outcome) %>%
    replace_na(list(retreat = "NR"))
}

# INTERFACE DEFINITION AND COMMAND LINE IMPLEMENTATION -------------------------

if (sys.nframe() == 0) {
  # p <- arg_parser("This is a template for executable R scripts.")
  # p <- add_argument(p, "foo", type = "character", nargs = 1,
  #                   help = "A positional command-line argument")
  # p <- add_argument(p, "--bar", type = "integer", default = 0,
  #                   nargs = 1, help = "A command-line option")
  # p <- add_argument(p, "--baz", flag = TRUE, help = "A command-line flag")

  # cl_args <- parse_args(p)
  cl_args <- cl_args[!(names(cl_args) %in% c("help", "opts"))]
  if (any(sapply(cl_args, is.na))) {
    # User did not specify all inputs; print help message
    print(p)
    cat("\n\nNot all needed inputs were given.\n")
    quit()
  }

  do.call(main, cl_args[2:length(cl_args)])
}

