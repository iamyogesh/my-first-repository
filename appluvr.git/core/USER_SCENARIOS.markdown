# V2 User - Primary Usage Scenarios

This document outlines the primary usage scenarios for a v2 Appluvr
user, with focus on how the anonymous and logged-in (FB) flows differ,
and how multi-device usage is handled.

## Data Structures

### Anonymous User

User Object - Random ID (Primary Key)

Device Object - Device UDID (Primary Key)

New user creation via a new URI (TBD) - will either initialize a new user + device or return existing user state URI

/users/<udid>/device/<udid>/...

All anonymous users have a random unique identifier and name, and are
associated with a single device.

### Facebook User

User Object - Facebook ID (Primary Key)

/users/<fbid>/device/<udid>/...

Zero or More Device Objects

* Device Object 1 - Device UDID (Primary Key)
* Device Object 2 - Device UDID (Primary Key)
* Device Object 3 - Device UDID (Primary Key)

***

## Scenarios 

*Scenario 1*: Anonymous User

API: 

* Create user
* create device
* associate user with device
* send back user + device details.

*Scenario 2*: Anonymous User ---(logs in to FB) ---> Facebook User

API: 

* Scenario 1 +
* lookup fb user
* (2 a) if exists -> associate device with fb logged in state, associate device with existing fb user, delete old user 
* (2 b) if not exists -> associate device with fb logged in state, associate user with fb user state

*Scenario 3*: Anonymous User ---(logs in to FB)----> Facebook User ---(logs out of FB)---> Anonymous User

API:

* Scenario 2 +
* disassociate device with fb logged in state
* 3a) if fb user has other devices -> disassociate this device, create a new anon user, associate the device with that user
* 3b) if fb user has no other devices -> wipe all user data & anonymize

*Scenario 4*: Anonymous User ---(logs in to FB) ---> Facebook User ---(logs into second device)--> Facebook User (with 2 devices)

API:

* Scenario 1+ 2a)

*Scenario 5*: Anonymous User ---(logs in to FB) ---> Facebook User ---(logs into second device)--> Facebook User (with 2 devices)-->(logs out of first device)--> Anonymous User + Facebook User

API:
* Scenario 4 + 3a)

*Scenario 6*: Anonymous User ---(logs in to FB) ---> Facebook User --- (factory reset or uninstall/reinstall) ---> Anonymous User --->  (logs in to FB) --- >


*Scenario 6a*: Anonymous User ---(logs in to FB) ---> Facebook User --- (factory reset or uninstall/reinstall) ---> Anonymous User --->  (logs in to FB) --- > Facebook User (UDID NOT changed > treated as first device)

*Scenario 6b*: Anonymous User ---(logs in to FB) ---> Facebook User --- (factory reset or uninstall/reinstall) ---> Anonymous User --->  (logs in to FB) --- > Facebook User (UDID  changed)   // in v2.5  treated as second device, in 2.0 it will just be another user

*Scenario 6c*: Anonymous User ---(logs in to FB) ---> Facebook User --- (factory reset or uninstall/reinstall) ---> Anonymous User --->  (logs in to different FB) --- > Facebook User 2 (UDID NOT changed > device moved from FB user 1 to FB user 2)

*Scenario 6d*: Anonymous User ---(logs in to FB) ---> Facebook User --- (factory reset or uninstall/reinstall) ---> Anonymous User --->  (logs in to different FB) --- > Facebook User 2 (UDID changed >  device 2 attached FB user 2, original device 1 attached to FB user 1)

*Scenario 7a*: 1.0 User -- (logs in to FB)  --> Upgrades to 2.0

Update in place, no backend changes expected.

*Scenario 7b*: 1.0 User -- (logs in to FB) --- (factory reset or uninstall/install) --> Upgrades to 2.0

Same scenario as returning 2.0 user

*Scenario 7c*: 1.0 User -- (not logged in or Logs out of FB) --> Upgrades to 2.0 (Logs in to FB)

Update in place, no backend changes expected.

*Scenario 7d*: 1.0 User -- (not logged in or Logs out of FB) --> Upgrades to 2.0 (does not Log in to FB)

Update in place, no backend changes expected.

*Scenario 8a*: 1.0 User ---(logs out of FB) ---> Upgrades to 2.0

Update in place, no backend changes expected.

*Scenario 8b*: 1.0 User -- (logs out to FB) --- (factory reset or uninstall/install) --> Upgrades to 2.0

*Scenario 9*: 1.0 User --- (logs in to FB) on Device 1,  setups 2.0 on Device 2, logs in to FB

*Scenarion 10*: 1.0 User --- (logs in to FB) on Device 1,  setups 2.0 on Device 2, logs in to FB, upgrades Device 1 to 2.0

*Scenario 10b*: 1.0 User -- (not logged in FB) on Device 1, setsup 2.0 on Device 2, logs in to FB on Dev2, upgrades Device 1 to 2.0 (and logs in to FB on Dev 1)


*Scenario 10c*: 1.0 User -- (not logged in FB) on Device 1, setsup 2.0 on Device 2, logs in to FB on Dev2, upgrades Device 1 to 2.0 (and does not log in to FB on dev1)


**NOTE:**
Whenever an FB user logged out and anonimizes all device specific personalization is reset ie OptIn, Installed App List


** Need to flesh out 1.0 -> 2.0 upgrade scenarios (where settings need to be migrated to user) **

***

*Anonymous -> Facebook*

* A new user gets created with the FB ID as Primary, device gets associated
* Old anonymous user gets deleted

*Facebook -> Anonymous*

* A new anonymous user gets created with the Device UDID as Primary, device gets associated
* If the FB user has no devices associated, it is still kept around for the FB Web App.


