from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from .models import *
from .constants import *
from .calculations import *
from .helper_classes import *
from .tables import *
from django.contrib.auth.decorators import login_required
from django.templatetags.static import static
from io import BytesIO
import base64
from django_tables2 import SingleTableView
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages

import numpy as np
import time
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# Remember that Django uses the word View to mean the Controller in MVC.  Django's "Views" are the HTML templates. Models are models.

@login_required
def headquarters(request):
    status = get_object_or_404(UserStatus, user=request.user)
    context = {"status": status,
               "page_title": "Headquarters"}
    return render(request, "headquarters.html", context)


@login_required
def council(request):
    status = get_object_or_404(UserStatus, user=request.user)
    constructions = Construction.objects.filter(user=request.user)
    # Make list of total buildings under construction for each building type
    build_list = {}
    for construction in constructions:
        label = construction.get_building_type_display() # get_X_display() is the trick for getting the full label of the textchoice
        build_list[label] = build_list.get(label, 0) + construction.n
    context = {"status": status,
               "constructions": constructions,
               "build_list": build_list,
               "page_title": "Council"}
    return render(request, "council.html", context)


@login_required
def map(request):
    if request.GET.get('heatmap', None):
        start_t = time.time()
        portals = Planet.objects.filter(portal=True).values_list('x', 'y')
        print("Found", len(portals), "portals")
        heatmap = np.zeros((100,100))
        for x in range(100):
            for y in range(100):
                for portal in portals:
                    d = np.sqrt((x-portal[0])**2 + (y-portal[1])**2)
                    research_culture = 0
                    cover = np.max((0, 1.0 - np.sqrt(d/(7.0*(1.0 + 0.01*research_culture))))) # from battlePortalCalc()
                    #specopForcefield = specopForcefieldCalc(planet_owner, feel_destinaton) # in specop.c, I haven't converted it over yet
                    #cover /= (1.0 + 0.01*specopForcefield)
                    heatmap[y,x] += cover # FIXME no idea why but i had to swap x and y for it to match planets...
        heatmap /= np.max(np.max(heatmap))
        colors = [(0.0, 0.0, 0.0), (0.0, 0.0, 1.0)] # black to blue colormap
        cm = LinearSegmentedColormap.from_list('custom-cmap', colors, N=20)
        plt.imsave(static('heatmap.png'), heatmap, cmap=cm)
        print("Heatmap generation took this many seconds:", time.time() - start_t)
        show_heatmap = True
    else:
        show_heatmap = False
    status = get_object_or_404(UserStatus, user=request.user)
    systems = Planet.objects.filter(i=0).values_list('x', 'y') # result is a list of 2-tuples
    context = {"status": status,
               "planets": Planet.objects.all(),
               "systems": systems, "page_title": "Map", "show_heatmap": show_heatmap}
    return render(request, "map.html", context)


@login_required
def planets(request):
    status = get_object_or_404(UserStatus, user=request.user)
    order_by = request.GET.get('order_by', 'planet')
    print("order by-", order_by)

    # TODO, it currently does not support reversing the order by clicking it a second time
    if order_by == 'planet':
        planets = Planet.objects.filter(owner=request.user).order_by('x','y','i')
    elif order_by in ['ancient','bonus_all','bonus_none','fission']:
        print("Havent implemented that sort yet")
        planets = Planet.objects.filter(owner=request.user).order_by('x','y','i')
    else:
        planets = Planet.objects.filter(owner=request.user).order_by(order_by) # directly use the keyword

    context = {"status": status,
               "planets": planets,
               "page_title": "Planets"}
    return render(request, "planets.html", context)


@login_required
def planet(request, planet_id):
    status = get_object_or_404(UserStatus, user=request.user)
    planet = get_object_or_404(Planet, pk=planet_id)

    if planet.owner: # if planet is owned by someone, grab that owner's status, in order to get faction and other info of owner
        planet_owner_status = UserStatus.objects.get(user=planet.owner)
    else:
        planet_owner_status = None

    context = {"status": status,
               "planet": planet,
               "planet_owner_status": planet_owner_status,
               "page_title": "Planet " + str(planet.x) + ',' + str(planet.y) + ':' + str(planet.i)}
    return render(request, "planet.html", context)


@login_required
def raze(request, planet_id):
    status = get_object_or_404(UserStatus, user=request.user)
    planet = get_object_or_404(Planet, pk=planet_id)

    # Make sure its owned by user
    if planet.owner != request.user:
        return HttpResponse("This is not your planet!")

    if request.method == 'POST':
        #print(request.POST)
        # List of building types, except portals
        building_list = [SolarCollectors(), FissionReactors(), MineralPlants(), CrystalLabs(), RefinementStations(), Cities(), ResearchCenters(), DefenseSats(), ShieldNetworks()]
        top_msg = ''
        for building in building_list:
            num_to_raze = request.POST.get(building.short_label, None) # number user entered to raze for this building type
            if num_to_raze == 'on':
                num_to_raze = 1
            elif num_to_raze:
                num_to_raze = int(num_to_raze)
            else:
                num_to_raze = 0
            num_on_planet = getattr(planet, building.model_name)  # This is how to access a field of a model using a string for the name of that field
            if (num_to_raze > 0) and (num_on_planet >= num_to_raze):
                setattr(planet, building.model_name, num_on_planet - num_to_raze)
                setattr(planet, 'total_buildings', getattr(planet, 'total_buildings') - num_to_raze)
                setattr(status, 'total_' + building.model_name, getattr(status, 'total_' + building.model_name) - num_to_raze)
                setattr(status, 'total_buildings', getattr(status, 'total_buildings') - num_to_raze)
                top_msg += "You razed " + str(num_to_raze) + " " + building.label + "<p><p>"
            elif num_to_raze > 0:
                top_msg += "Did not have " + str(num_to_raze) + " " + building.label + " to raze<p><p>"
        # Do portal separately
        if request.POST.get("PL", None) and planet.portal:
            planet.portal = False
            top_msg += "You razed the Portal on this planet<p><p>"
        elif request.POST.get("PL", None):
            top_msg += "There is no Portal on this planet to raze<p><p>"
        # Any time we change buildings we need to update planet's overbuild factor
        planet.overbuilt = calc_overbuild(planet.size, planet.total_buildings + planet.buildings_under_construction)
        planet.overbuilt_percent = (planet.overbuilt-1.0)*100
        # Save our changes to planet and status
        planet.save()
        status.save()
    else:
        top_msg = None

    context = {"status": status,
               "planet": planet,
               "top_msg": top_msg,
               "page_title": "Raze Buildings on Planet " + str(planet.x) + ',' + str(planet.y) + ':' + str(planet.i)}
    return render(request, "raze.html", context)


@login_required
def razeall(request, planet_id): #TODO still need an html template for this page
    status = get_object_or_404(UserStatus, user=request.user)
    planet = get_object_or_404(Planet, pk=planet_id)
    if request.method == 'POST':
        # List of building types, except portals
        building_list = [SolarCollectors(), FissionReactors(), MineralPlants(), CrystalLabs(), RefinementStations(), Cities(), ResearchCenters(), DefenseSats(), ShieldNetworks()]
        for building in building_list:
            num_on_planet = getattr(planet, building.model_name)
            if num_on_planet:
                setattr(planet, building.model_name, 0)
                setattr(status, 'total_' + building.model_name, getattr(status, 'total_' + building.model_name) - num_on_planet)
                setattr(status, 'total_buildings', getattr(status, 'total_buildings') - num_on_planet)
        setattr(planet, 'total_buildings', 0)
        # Portal
        if planet.portal:
            planet.portal = False
            setattr(status, 'total_portals', getattr(status, 'total_portals') - 1)
            setattr(status, 'total_buildings', getattr(status, 'total_buildings') - 1)
        # Any time we change buildings we need to update planet's overbuild factor
        planet.overbuilt = calc_overbuild(planet.size, planet.total_buildings + planet.buildings_under_construction)
        planet.overbuilt_percent = (planet.overbuilt-1.0)*100
        planet.save()
        status.save()
        return HttpResponse("Razed all buildings on this planet!")
    else:
        return HttpResponse("CAN ONLY GET HERE BY CLICKING RAZE ALL BUTTON")


@login_required
def build(request, planet_id):
    # This entire view + template is reproducing iohtmlFunc_build()

    status = get_object_or_404(UserStatus, user=request.user)
    planet = get_object_or_404(Planet, pk=planet_id)

    # Make sure its owned by user
    if planet.owner != request.user:
        return HttpResponse("This is not your planet!")

    # Create list of building classes, it's making 1 object of each
    building_list = [SolarCollectors(), FissionReactors(), MineralPlants(), CrystalLabs(), RefinementStations(), Cities(), ResearchCenters(), DefenseSats(), ShieldNetworks(), Portal()]

    if request.method == 'POST':
        # Might be a cleaner way to do it that ties it more directly with the model

        # Following is a rewrite of cmdExecAddBuild in cmd.c, a function that got called for each building type
        msg = ''
        for building in building_list:
            num = request.POST.get(str(building.building_index), None)
            if num == 'on':
                num = 1
            if num == '':
                num = None
            if num:
                num = int(num)
                # calc_building_cost was designed to give the View what it needed, so pull out just the values and multiply by num
                total_resource_cost, penalty = building.calc_cost(num, status.research_percent_construction, status.research_percent_tech)
                if not total_resource_cost:
                    msg += 'Not enough tech research to build ' + building.label + '<br>'
                    continue

                total_resource_cost = ResourceSet(total_resource_cost) # convert to more usable object
                ob_factor = calc_overbuild_multi(planet.size, planet.total_buildings + planet.buildings_under_construction, num)
                total_resource_cost.apply_overbuild(ob_factor) # can't just use planet.overbuilt, need to take into account how many buildings we are making

                if not total_resource_cost.is_enough(status):
                    msg += 'Not enough resources to build ' + building.label + '<br>'
                    continue

                if isinstance(building, Portal) and planet.portal:
                    msg += 'A portal is already on this planet!'
                    continue

                if isinstance(building, Portal) and planet.portal_under_construction:
                    msg += 'A portal is already under construction on this planet!'
                    continue

                # Deduct resources
                status.energy    -= total_resource_cost.ene
                status.minerals  -= total_resource_cost.min
                status.crystals  -= total_resource_cost.cry
                status.ectrolium -= total_resource_cost.ect

                ticks = total_resource_cost.time # calculated ticks

                # Create new construction job
                msg += 'Building ' + str(num) + ' ' + building.label + '<br>'
                Construction.objects.create(user=request.user,
                                            planet=planet,
                                            n=num,
                                            building_type=building.short_label,
                                            ticks_remaining=ticks)
                planet.buildings_under_construction += num
                if isinstance(building, Portal):
                    planet.portal_under_construction = True

        # Any time we add buildings we need to update planet's overbuild factor
        planet.overbuilt = calc_overbuild(planet.size, planet.total_buildings + planet.buildings_under_construction)
        planet.overbuilt_percent = (planet.overbuilt-1.0)*100
        planet.save()
        status.save() # update user's resources
    else:
        msg = None # msg that gets displayed at the top after you build something

    # Build up list of dicts, designed to be used easily by template
    costs = []
    for building in building_list:
        # Below doesn't include overbuild, it gets added below
        cost_list, penalty = building.calc_cost(1, status.research_percent_construction, status.research_percent_tech)

        # Add resource names to the cost_list, for the sake of the for loop in the view
        if cost_list: # Remember that cost_list will be None if the tech is too low
            cost_list_labeled = []
            for i in range(5): # 4 types of resources plus time
                cost_list_labeled.append({"value": int(np.ceil(cost_list[i]*planet.overbuilt)),
                                          "name": resource_names[i]})
        else:
            cost_list_labeled = None # Tech was too low

        cost = {"cost": cost_list_labeled,
                "penalty": penalty,
                "owned": getattr(status, 'total_' + building.model_name),
                "name": building.label}
        costs.append(cost)

    # Build context
    context = {"status": status,
               "planet": planet,
               "costs": costs,
               "portal": planet.portal,
               "portal_under_construction": planet.portal_under_construction,
               "msg": msg,
               "page_title": "Build on Planet " + str(planet.x) + ',' + str(planet.y) + ':' + str(planet.i)}
    return render(request, "build.html", context)


@login_required
def ranking(request):
    status = get_object_or_404(UserStatus, user=request.user)
    table = UserRankTable(UserStatus.objects.all(), order_by=("-num_planets"))
    context = {"table": table,
               "status": status}
    return render(request, "ranking.html", context)


@login_required
def account(request):
    status = get_object_or_404(UserStatus, user=request.user)
    context = {"status": status}
    return render(request, "account.html", context)


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('change_password')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'change_password.html', {
        'form': form
    })


@login_required
def units(request):
    status = get_object_or_404(UserStatus, user=request.user)
    if request.method == 'POST':
        print(request.POST)
        msg = ''
        for i, unit in enumerate(unit_info["unit_list"]):
            if unit == 'phantom':
                continue
            num = request.POST.get(str(i), 0)  # must match name of each inputfield in the template, in this case we are using integers
            if num == '':
                num = 0
            else:
                num = int(num)
            if num:
                # calc_building_cost was designed to give the View what it needed, so pull out just the values and multiply by num
                mult, _ = unit_cost_multiplier(status.research_percent_construction, status.research_percent_tech, unit_info[unit]['required_tech'])
                if not mult:
                    msg += 'Not enough tech research to build ' + unit_info[unit]['label'] + '<br>'
                    continue

                print("multiplier:", mult)
                total_resource_cost = [int(np.ceil(x*mult)) for x in unit_info[unit]['cost']]
                for j in range(4): # multiply all resources except time by number of units
                    total_resource_cost[j] *= num
                print("total_resource_cost", total_resource_cost)
                total_resource_cost = ResourceSet(total_resource_cost) # convert to more usable object
                if not total_resource_cost.is_enough(status):
                    msg += 'Not enough resources to build ' + unit_info[unit]['label'] + '<br>'
                    continue

                # Deduct resources
                status.energy    -= total_resource_cost.ene
                status.minerals  -= total_resource_cost.min
                status.crystals  -= total_resource_cost.cry
                status.ectrolium -= total_resource_cost.ect

                # Create new construction job
                msg += 'Building ' + str(num) + ' ' + unit + '<br>'
                UnitConstruction.objects.create(user=request.user,
                                                n=num,
                                                unit_type=unit,
                                                ticks_remaining=total_resource_cost.time) # calculated ticks

        status.save() # update user's resources
    else:
        msg = None

    resource_names = ['Energy','Mineral','Crystal','Ectrolium','Time']
    unit_dict = [] # idea here is to build up a dict we can nicely iterate over in the template
    for unit in unit_info["unit_list"]:
        if unit == 'phantom':
            continue
        d = {}
        mult, penalty = unit_cost_multiplier(status.research_percent_construction, status.research_percent_tech, unit_info[unit]['required_tech'])
        if not mult:
            cost = None
        else:
            cost = []
            for i, resource in enumerate(resource_names):
                cost.append({"name": resource, "value": int(np.ceil(mult*unit_info[unit]['cost'][i]))})
            d["cost"] = cost
        d["penalty"] = penalty
        d["label"] = unit_info[unit]['label']
        d["owned"] = 0
        d["i"] = unit_info[unit]['i']
        unit_dict.append(d)
    context = {"status": status,
               "unit_dict": unit_dict,
               "msg": msg}
    return render(request, "units.html", context)


@login_required
def fleets(request):
    status = get_object_or_404(UserStatus, user=request.user)

    # If user changed order after attack or percentages
    if request.method == 'POST':
        status.post_attack_order = int(request.POST["attack"])
        status.long_range_attack_percent = int(request.POST["f0"])
        status.air_vs_air_percent        = int(request.POST["f1"])
        status.ground_vs_air_percent     = int(request.POST["f2"])
        status.ground_vs_ground_percent  = int(request.POST["f3"])
        status.save()

    main_fleet = Fleet.objects.get(owner=status.user.id, main_fleet=True) # should only ever be 1
    main_fleet_list = []
    send_fleet_list = [] # need to have a separate list that doesnt include agents/psycics/ghosts/explos
    for unit in unit_info["unit_list"]:
        num = getattr(main_fleet, unit)
        if num:
            main_fleet_list.append({"name": unit_info[unit]["label"], "value": num, "i": unit_info[unit]["i"]})
            if unit not in ['wizard','agent','ghost','exploration']:
                send_fleet_list.append({"name": unit_info[unit]["label"], "value": num, "i": unit_info[unit]["i"]})

    # TODO Generate list of traveling and stationed fleets (in old game i dont see anywhere a list of stationed fleets is shown)

    context = {"status": status,
               "main_fleet_list": main_fleet_list,
               "send_fleet_list": send_fleet_list}
    return render(request, "fleets.html", context)



@login_required
def fleetsend(request):
    status = get_object_or_404(UserStatus, user=request.user)
    round_params = get_object_or_404(RoundParams) # should only be one
    main_fleet = Fleet.objects.get(owner=status.user.id, main_fleet=True) # should only ever be 1

    if request.method != 'POST':
        return HttpResponse("You shouldnt be able to get to this page!")

    # Process POST
    print(request.POST)
    x = int(request.POST['X']) if request.POST['X'] else None
    y = int(request.POST['Y']) if request.POST['Y'] else None
    planet_i = int(request.POST['I']) if request.POST['I'] else None
    order = int(request.POST['order'])
    send_unit_dict = {} # contains how many of each unit to send, dict so its quick to look up different unit counts
    total_sent_units = 0
    for i, unit in enumerate(unit_info["unit_list"][0:9]):
        num = int(request.POST['u'+str(i)]) if request.POST['u'+str(i)] else 0
        if getattr(main_fleet, unit) < num:
            return HttpResponse("Don't have enough" + unit_info[unit]["label"])
        send_unit_dict[unit] = num
        total_sent_units += num

    if total_sent_units == 0:
        return HttpResponse("You must send some units to make a fleet")

    # The rest mostly comes from cmdExecSendFleet in cmdexec.c
    if order == 0 or order == 1: # if attack planet or station on planet, make sure planet exists and get planet object
        try:
            planet = Planet.objects.get(x=x,y=y,i=planet_i)
        except Planet.DoesNotExist:
            return HttpResponse("This planet doesn't exist")
    else: # if move to system, make sure x and y are actual coords
        if x < 0 or x >= round_params.galaxy_size or y < 0 or y >= round_params.galaxy_size:
            return HttpResponse("Coordinates aren't valid")

    # Find closest portal and its distance away, which is done in specopVortexListCalc in cmd.c in the C code
    portal_planets = Planet.objects.filter(owner=request.user, portal=True) # should always have at least the home planet
    min_dist = 9999999999
    best_portal_planet = None
    for planet in portal_planets:
        dist = np.sqrt((planet.x - x)**2 + (planet.y - y)**2)
        if dist < min_dist:
            min_dist = dist
            best_portal_planet = planet
    print("Fleet is starting from", best_portal_planet.x, best_portal_planet.y)

    speed = race_info_list[status.get_race_display()]["travel_speed"]  # * specopEnlightemntCalc(id,CMD_ENLIGHT_SPEED);
    # CODE for artefact that decreases/increases travel speed by n%
    # if ( maind.artefacts & ARTEFACT_4_BIT)
    # fa *= 0.8
    fleet_time = int(np.ceil(min_dist / speed)) # in ticks

    # Carrier/transport check
    if send_unit_dict['carrier']*100 < (send_unit_dict['bomber'] + send_unit_dict['fighter'] + send_unit_dict['transport']):
        return HttpResponse("You are not sending enough carriers, each carrier can hold 100 fighters, bombers or transports")
    if send_unit_dict['transport']*100 < (send_unit_dict['soldier'] + send_unit_dict['droid'] + 4*send_unit_dict['goliath']):
        return HttpResponse("You are not sending enough transports, each transport can hold 100 soldiers or droids, or 25 goliaths")

    # Remove units from main fleet
    for unit in unit_info["unit_list"][0:9]:
        setattr(main_fleet, unit, getattr(main_fleet, unit) - send_unit_dict[unit])

    # Create new Fleet object
    Fleet.objects.create(owner=request.user,
                         command_order = order,
                         x=x,
                         y=y,
                         ticks_remaining = fleet_time)


    # If instant travel then immediately do the cmdFleetAction stuff
    if fleet_time == 0:
        # TODO
        # cmdFleetAction()
        return HttpResponse("The fleet reached its destination<br>")

    return HttpResponse("The fleet will reach its destination in " + str(fleet_time) + " weeks<br>")







# TODO, COPY FROM RAZE VIEW
@login_required
def fleetdisband(request):
    status = get_object_or_404(UserStatus, user=request.user)
    return HttpResponse("GOT HERE")











