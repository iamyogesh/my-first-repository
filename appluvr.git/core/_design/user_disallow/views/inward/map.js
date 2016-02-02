function (doc) {
 if (doc.doc_type == 'user_disallow'){
  if (!!doc.me){
   if (doc.blocked_friends !== ""){
    var blocked_friends = doc.blocked_friends.split(',');
    if (blocked_friends.length>0) {
       for (var i = 0; i < blocked_friends.length; i++ ){
          friend = blocked_friends[i].replace(/^\s+|\s+$/g,'')
          emit(friend, doc.me);
       }
    }
   }
  }
 }
}