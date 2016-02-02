function (head, req) {
  
  //Process each row/doc, collate same values and count.
  var data = [], total = 0, placeHolder = {};
  while ( row = getRow() ) {
    var k = row.key[2]+" "+row.key[3]+" "+row.key[4];
    
    if(placeHolder[k]){
      placeHolder[k]=placeHolder[k]+row.value;
    } else {
      placeHolder[k]=row.value;
    }

    total=total+row.value;    
  } 
  
  //Repack into an array.
  for(var itm in placeHolder){
    var temp = {name: "", count: ""};
    temp.name = itm;
    temp.count = placeHolder[itm];    
    data.push(temp);    
  }

  send(toJSON({"data":data,"total":total}));
  
}