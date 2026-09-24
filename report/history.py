"""
Velocity history across previous sprints, and committed-vs-completed per sprint.

Definitions:
  velocity of a past sprint = SP of Done stories, each story counted once,
                              against the most recent of its sprints that is
                              in the history window
  committed of a past sprint = SP of every story that was in that sprint
                              (a carried-over story counts in each sprint it was in)
"""

import pandas as pd

from . import issues as iss


def previous_sprints(all_sprints, selected, how_many):
    """The `how_many` sprints just before `selected` in the configured list."""
    index = all_sprints.index(selected)
    return all_sprints[max(0, index - how_many):index]


def velocity_by_sprint(done_issues, sprints):
    """{sprint name: delivered SP} for the given sprints."""
    velocity = {sprint: 0 for sprint in sprints}
    for issue in done_issues:
        for name in reversed(iss.sprint_names(issue)):          # most recent sprint first
            if name in velocity:
                velocity[name] += iss.story_points(issue)
                break
    return velocity


def committed_by_sprint(all_issues, sprints):
    """{sprint name: committed SP} for the given sprints."""
    committed = {sprint: 0 for sprint in sprints}
    for issue in all_issues:
        for name in iss.sprint_names(issue):
            if name in committed:
                committed[name] += iss.story_points(issue)
    return committed


def history_tables(sprints, velocity, committed, selected, selected_committed, selected_delivered):
    """
    historical_df      Sprint | Velocity             (previous sprints only)
    average_velocity   mean of that Velocity column (0 when there is no history)
    sprint_history_df  Sprint | Committed | Completed (previous sprints + selected)
    """
    historical_df = pd.DataFrame(
        [{"Sprint": s, "Velocity": velocity.get(s, 0)} for s in sprints],
        columns=["Sprint", "Velocity"],
    )
    average_velocity = (round(float(historical_df["Velocity"].mean()), 2)
                        if not historical_df.empty else 0)

    sprint_history_df = pd.DataFrame(
        [{"Sprint": s, "Committed": committed[s], "Completed": velocity[s]} for s in sprints]
        + [{"Sprint": selected, "Committed": selected_committed, "Completed": selected_delivered}],
        columns=["Sprint", "Committed", "Completed"],
    )
    return historical_df, average_velocity, sprint_history_df
