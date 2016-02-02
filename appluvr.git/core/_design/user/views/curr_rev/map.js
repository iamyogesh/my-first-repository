function (doc) {
if (doc.doc_type == 'user'){
emit(doc.modified, null);
}
}
