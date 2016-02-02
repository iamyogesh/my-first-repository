function (head, req) {
  //Array Sorting function
  var sortByAppCount = function (a,b){ return b.count - a.count; }

  //Placeholder for result.
  var row, top=50, total=0;  
 
  //Process each row/doc, push into an array for sorting.
  var data = {name: "",count:0}, sortArr=[];
  while ( row = getRow() ) {
    var temp = {name: "",count: ""}
    temp.name = row.key[2];
    temp.count = row.value;
    sortArr.push(temp);    
  }
  
  sortArr.sort(sortByAppCount);
  

  if(sortArr.length<top) top=sortArr.length;
  sortArr = sortArr.splice(0, top-1);

  //Counting
  for(var v=0; v<sortArr.length; v++) total = total+sortArr[v].count;

  var result = {"data": sortArr,"total":total};
  send(toJSON(result));
}