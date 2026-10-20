<script setup>


defineProps({

title:String,

value:String,

unit:String,

status:String

})


</script>




<template>


<div class="card">


<div class="title">

{{title}}

</div>



<div class="value">

{{value}}

</div>


<div class="unit">

{{unit}}

</div>


<div class="status">

{{status}}

</div>


</div>


</template>






<style scoped>


.card{


height:120px;

background:white;

border-radius:15px;

display:flex;

flex-direction:column;

align-items:center;

justify-content:center;


box-shadow:

0 5px 15px rgba(0,0,0,.08);


}



.title{


font-size:16px;

color:#666;


}



.value{


font-size:34px;

font-weight:bold;

color:#606080;

line-height:1.1;


}



.unit{


font-size:13px;

color:#999;


}



.status{


margin-top:8px;

font-size:14px;

color:#666;


}


</style>