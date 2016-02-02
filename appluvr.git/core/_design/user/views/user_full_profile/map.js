function(doc){
  //Process only "user" docs.
  if(doc.doc_type == "user"){

    var apps_liked = [], interests_liked = [], apps_disliked = [], fb_id = null;
    //Mark FB Login status
    var userHasNoDevices = true;   
        
    //Link and output all associated devices for this user to list for processing.
    var links = doc.links;
    var udid = null;

    //Prepare user profile details.
    if(doc.apps_liked) apps_liked = doc.apps_liked;
    if(doc.apps_disliked) apps_disliked = doc.apps_disliked;
    if(doc.interests) interests_liked = doc.interests;
    if(doc.fb_id) fb_id = doc.fb_id;

    for(var i=0;i<links.length;i++){
      if(links[i].rel == 'device'){
        udid = links[i].href;
        if(udid){          
          userHasNoDevices=false;          
          emit(doc._id, {_id:udid, fb_id:fb_id, apps_liked:apps_liked, apps_disliked:apps_disliked, interests_liked:interests_liked});
        }
      }
    }

    //Even if a user has no devices it needs to get listed.
    if(userHasNoDevices){
      emit(doc._id, {_id:null, fb_id:fb_id, apps_liked:apps_liked, apps_disliked:apps_disliked, interests_liked:interests_liked});
    }
  }
}
