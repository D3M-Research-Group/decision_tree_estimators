import copy

import numpy as np
from gurobipy import LinExpr, quicksum

# helper functions for BenderOCT callback


def get_left_exp_integer(main_grb_obj, n, i):
    lhs = quicksum(
        -1 * main_grb_obj.b[n, f]
        for f in main_grb_obj.X_col_labels
        if main_grb_obj.X.at[i, f] == 0
    )

    return lhs


def get_right_exp_integer(main_grb_obj, n, i):
    lhs = quicksum(
        -1 * main_grb_obj.b[n, f]
        for f in main_grb_obj.X_col_labels
        if main_grb_obj.X.at[i, f] == 1
    )

    return lhs


def get_target_exp_integer(main_grb_obj, n, i):
    label_i = main_grb_obj.y[i]
    lhs = -1 * main_grb_obj.w[n, label_i]
    return lhs


def get_cut_integer(main_grb_obj, left, right, target, i):
    lhs = LinExpr(0) + main_grb_obj.g[i]
    for n in left:
        tmp_lhs = get_left_exp_integer(main_grb_obj, n, i)
        lhs = lhs + tmp_lhs

    for n in right:
        tmp_lhs = get_right_exp_integer(main_grb_obj, n, i)
        lhs = lhs + tmp_lhs

    for n in target:
        tmp_lhs = get_target_exp_integer(main_grb_obj, n, i)
        lhs = lhs + tmp_lhs

    return lhs


# helper functions for RobustTree callback


def get_cut_expression(master, b, w, path, xi, v, i):
    expr = LinExpr(0)
    node_leaf_cutoff = np.power(
        2, master.tree.depth
    )  # anything at or above this number is a leaf

    # Add expressions to rhs where q = 1
    for x in range(len(path)):
        n = path[x]  # Current node
        if n < node_leaf_cutoff:
            if x == len(path) - 1:
                # Assigned a value at an internal node
                expr += quicksum(
                    master.b[n, f, theta] for (f, theta) in master.f_theta_indices
                )
            # Add to expr if we went right according to our shortest path
            elif (2 * n) + 1 == path[x + 1]:
                expr += quicksum(
                    master.b[n, f, theta]
                    for (f, theta) in master.f_theta_indices
                    if (master.X.at[i, f] + xi[f] <= theta)
                )
            # Add to expr if we went left according to our shortest path
            else:
                expr += quicksum(
                    master.b[n, f, theta]
                    for (f, theta) in master.f_theta_indices
                    if (master.X.at[i, f] + xi[f] >= theta + 1)
                )
        # Add to expr the node going to the sink
        if not (x == len(path) - 1 and v):
            # Don't add edge to sink if at assignment node and label is changed
            expr += master.w[n, master.y[i]]
        else:
            expr += quicksum(
                master.w[n, lab] for lab in master.labels if (lab != master.y[i])
            )
    return expr


def get_all_terminal_paths(
    master,
    b,
    w,
    terminal_nodes=[],
    path_dict={},
    feature_path_dict={},
    assignment_dict={},
    cutoff_dict={},
    cat_dict={},
    curr_node=1,
    curr_path=[1],
    curr_feature_path=[],
    curr_cutoff_path=[],
    curr_cat_path=[],
):
    """find all terminal paths"""
    new_path_dict = copy.deepcopy(path_dict)
    new_terminal_nodes = copy.deepcopy(terminal_nodes)
    new_feature_path_dict = copy.deepcopy(feature_path_dict)
    new_assignment_dict = copy.deepcopy(assignment_dict)
    new_cutoff_dict = copy.deepcopy(cutoff_dict)
    new_cat_dict = copy.deepcopy(cat_dict)

    for k in master.labels:
        if w[curr_node, k] > 0.5:  # w[n,k] == 1
            # assignment node
            new_path_dict[curr_node] = curr_path
            new_terminal_nodes += [curr_node]
            new_feature_path_dict[curr_node] = curr_feature_path
            new_assignment_dict[curr_node] = k
            new_cutoff_dict[curr_node] = curr_cutoff_path
            new_cat_dict[curr_node] = curr_cat_path
            return (
                new_terminal_nodes,
                new_path_dict,
                new_feature_path_dict,
                new_assignment_dict,
                new_cutoff_dict,
                new_cat_dict,
            )

    # b[n,f,theta]== 1
    curr_feature = None
    curr_theta = None
    curr_cat = False
    for (f, theta) in master.f_theta_indices:
        if b[curr_node, f, theta] > 0.5:
            curr_feature = f
            curr_theta = theta
            if f in master.inverse_categories.keys():
                curr_cat = master.inverse_categories[f]
            else:
                curr_cat = ""
            break

    # Go left
    left_node = master.tree.get_left_children(curr_node)
    left_path = curr_path + [left_node]
    (
        left_terminal,
        left_paths,
        left_feature,
        left_assign,
        left_cutoff,
        left_cat,
    ) = get_all_terminal_paths(
        master,
        b,
        w,
        terminal_nodes=terminal_nodes,
        path_dict=path_dict,
        feature_path_dict=feature_path_dict,
        assignment_dict=assignment_dict,
        cutoff_dict=cutoff_dict,
        cat_dict=cat_dict,
        curr_node=left_node,
        curr_path=left_path,
        curr_feature_path=curr_feature_path + [curr_feature],
        curr_cutoff_path=curr_cutoff_path + [curr_theta],
        curr_cat_path=curr_cat_path + [curr_cat],
    )

    # Go right
    right_node = master.tree.get_right_children(curr_node)
    right_path = curr_path + [right_node]
    (
        right_terminal,
        right_paths,
        right_feature,
        right_assign,
        right_cutoff,
        right_cat,
    ) = get_all_terminal_paths(
        master,
        b,
        w,
        terminal_nodes=terminal_nodes,
        path_dict=path_dict,
        feature_path_dict=feature_path_dict,
        assignment_dict=assignment_dict,
        cutoff_dict=cutoff_dict,
        cat_dict=cat_dict,
        curr_node=right_node,
        curr_path=right_path,
        curr_feature_path=curr_feature_path + [curr_feature],
        curr_cutoff_path=curr_cutoff_path + [curr_theta],
        curr_cat_path=curr_cat_path + [curr_cat],
    )

    new_path_dict.update(left_paths)
    new_path_dict.update(right_paths)
    new_terminal_nodes += left_terminal
    new_terminal_nodes += right_terminal
    new_feature_path_dict.update(left_feature)
    new_feature_path_dict.update(right_feature)
    new_assignment_dict.update(left_assign)
    new_assignment_dict.update(right_assign)
    new_cutoff_dict.update(left_cutoff)
    new_cutoff_dict.update(right_cutoff)
    new_cat_dict.update(left_cat)
    new_cat_dict.update(right_cat)

    return (
        new_terminal_nodes,
        new_path_dict,
        new_feature_path_dict,
        new_assignment_dict,
        new_cutoff_dict,
        new_cat_dict,
    )


def get_nominal_path(master, b, w, i):
    """Get the nominal path for a correctly classified point"""
    path = []
    curr_node = 1

    while True:
        path += [curr_node]
        # Find whether a terminal node
        for k in master.labels:
            if w[curr_node, k] > 0.5:
                return path, k

        # braching node - find which feature to branch on
        for (f, theta) in master.f_theta_indices:
            if b[curr_node, f, theta] > 0.5:
                if master.X.at[i, f] >= theta + 1:
                    curr_node = (2 * curr_node) + 1  # go right
                else:
                    curr_node = 2 * curr_node  # go left
                break


def shortest_path_solver(
    master,
    i,
    label,
    terminal_nodes,
    terminal_path_dict,
    terminal_features_dict,
    terminal_assignments_dict,
    terminal_cutoffs_dict,
    terminal_cat_dict,
    initial_xi,
    initial_mins,
    initial_maxes,
):
    best_cost = (master.epsilon + 1) * master.tree.depth
    best_path = []
    xi = copy.deepcopy(initial_xi)
    v = False

    for j in terminal_nodes:
        # Get cost of path
        curr_features = terminal_features_dict[j]
        curr_cutoffs = terminal_cutoffs_dict[j]
        curr_cat = terminal_cat_dict[j]
        curr_xi = copy.deepcopy(initial_xi)
        curr_v = terminal_assignments_dict[j] == label
        curr_mins = copy.deepcopy(initial_mins)
        curr_maxes = copy.deepcopy(initial_maxes)
        curr_path = terminal_path_dict[j]
        curr_cost = master.eta * int(
            curr_v
        )  # Start with cost if correctly classify point
        best_so_far = True
        for x in range(len(curr_path) - 1):
            n = curr_path[x]  # Current node
            f = curr_features[x]
            theta = curr_cutoffs[x]
            min_f = curr_mins[f]
            max_f = curr_maxes[f]
            cat_f = curr_cat[x]

            curr_value = master.X.at[i, f] + curr_xi[f]
            # Went right
            if (2 * n) + 1 == curr_path[x + 1]:  # Path goes right
                if curr_value <= theta:
                    # See if can switch to go right by increasing x to theta+1
                    if max_f < theta + 1:
                        # Impossible path
                        best_so_far = False
                        break
                    if cat_f != "":
                        # Categorical Feature
                        incur_cost = True
                        for cat_value in master.model.categories[cat_f]:
                            if curr_xi[cat_value] != 0:
                                # Don't need to add additional cost
                                incur_cost = False
                            if cat_value == f:
                                # Changing from 0 -> 1
                                curr_xi[f] = 1
                                curr_mins[cat_value] = 1
                            elif master.X.at[i, cat_value] == 1:
                                # Current value of category
                                if curr_mins[cat_value] == 0:
                                    # Impossible path
                                    best_so_far = False
                                    break
                                curr_maxes[cat_value] = 0
                                curr_xi[cat_value] = -1
                            else:
                                # Not current value of category
                                if curr_mins[cat_value] == 1:
                                    # Impossible path
                                    best_so_far = False
                                    break
                                curr_maxes[cat_value] = 0
                        if not best_so_far:
                            break
                        if incur_cost:
                            curr_cost += 2 * master.gammas.loc[i][f]
                    else:
                        # x + delta_x = theta + 1
                        delta_x = theta - master.X.at[i, f] + 1  # positive value

                        # cost increases by gamma per unit increase of xi
                        curr_cost += master.gammas.loc[i][f] * (delta_x - curr_xi[f])
                        curr_xi[f] = delta_x

                # Update bounds
                curr_mins[f] = max(curr_mins[f], theta + 1)

            else:  # Went left
                if curr_value >= theta + 1:
                    # See if can switch to go left by decreasing x to theta
                    if min_f > theta:
                        # Impossible path
                        best_so_far = False
                        break
                    if cat_f != "":
                        # Categorical Feature
                        incur_cost = True
                        changed = False
                        for cat_value in master.model.categories[cat_f]:
                            if curr_xi[cat_value] != 0:
                                # Don't need to add additional cost
                                incur_cost = False
                            if cat_value == f:
                                # Changing from 1 -> 0
                                curr_xi[f] = -1
                                curr_maxes[cat_value] = 0
                            elif not changed and curr_maxes[cat_value] == 1:
                                # Select this as new value
                                # Do NOT update mins in case want to change later
                                curr_xi[f] = 1
                                changed = True
                        if not changed:
                            # Could not find a value to set the categorical feature
                            best_so_far = False
                            break
                        if incur_cost:
                            curr_cost += 2 * master.gammas.loc[i][f]
                    # x + delta_x = theta
                    delta_x = theta - master.X.at[i, f]  # negative value

                    # cost increases by gamma per unit decrease of xi
                    curr_cost += master.gammas.loc[i][f] * (curr_xi[f] - delta_x)
                    curr_xi[f] = delta_x

                # Update bounds
                curr_maxes[f] = min(curr_maxes[f], theta)

            if curr_cost > best_cost:
                # No need to go further
                best_so_far = False
                break
        if best_so_far:
            best_cost = curr_cost
            best_path = curr_path
            xi = curr_xi
            v = curr_v

    return best_path, best_cost, xi, v
