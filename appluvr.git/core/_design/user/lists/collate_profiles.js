function (head, req) {

  //Placeholder for result.
  var apps_liked = [], interests_liked = [], apps_disliked = [], fb_id = null, createdUserProfile = false;
  var final_result = { device_profiles:[], uid:null, user_profile:null };
  var user_profile = { apps_liked:[], interests_liked:[], apps_disliked:[] } ;
  var device_profiles = [];
  
  //Process each row/doc, do create single user profile and as many device profiles as possible.
  while (row = getRow()) {

    //Empty device profile template.
    var dev_profile = { os_version:null, apps_installed:[], uid:null, model:null, manufacturer:null, odp_installed:null, number:null };
    
    //Create user profiles.
    if (!createdUserProfile){
      final_result.uid = row.key;
      user_profile.apps_liked = row.value["apps_liked"];
      user_profile.apps_disliked = row.value["apps_disliked"];
      user_profile.interests_liked = row.value["interests_liked"];
      createdUserProfile = true;
    }

    //Create device profiles.
    dev_profile.os_version = row.doc["os_version"];
    dev_profile.apps_installed = row.doc["apps_installed"];
    dev_profile.uid = row.doc["_id"];
    dev_profile.model = row.doc["model"];
    dev_profile.manufacturer = row.doc["manufacturer"];
    dev_profile.odp_installed = row.doc["odp_installed"];
    dev_profile.number = row.doc["number"];

    //Pile on all device profiles.
    device_profiles.push(dev_profile);
  }
  
  //Final Output.
  final_result.device_profiles = device_profiles;
  final_result.user_profile = user_profile;
  send(toJSON(final_result));

}