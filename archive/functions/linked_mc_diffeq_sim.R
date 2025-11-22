linked_mc_diffeq_sim <- function(stages, deltas) {

  # check args
  stopifnot(
    is_bare_numeric(deltas),
    is_bare_list(stages),
    length(stages) == length(deltas)
  )

  tibble(
    !!!setNames(
      rep(NA_real_, length(names(stages[[1]]$state))+1),
      c("time", names(stages[[1]]$state))), 
    .rows = 0
  ) -> init_df 

  reduce2(stages, deltas, \(acc, x, y) {

    # drop last row for binding
    if (nrow(acc) != 0) {
      df <- acc[1:(nrow(acc) - 1),]
    } else {
      df <- acc
    }

    # get last row
    final_state <- set_names(as.numeric(tail(acc, 1)), names(acc))
    final_state <- final_state[names(final_state) != "time"]

    if (any(is.na(final_state))) {
      final_state <- x$state
    }

    # run next model
    link <- markovchain_diffeq_sim(
      init = final_state,
      rate_func = x$rate_func,
      time = y
    )

    if (nrow(acc) != 0) {
      link$time <- link$time + max(acc$time)
    }

    # bind together and return
    df %>% 
      bind_rows(link) %>% 
      return()

  }, .init = init_df) %>% 
    return()

}