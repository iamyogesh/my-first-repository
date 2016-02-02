function (doc) {
if (doc.doc_type == 'user_disallow'){
if (!!doc.me)
emit(doc.me, doc.blocked_friends);
}
}
