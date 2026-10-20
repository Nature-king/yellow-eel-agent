<script setup>

import {
onMounted,
watch,
ref
}
from "vue"


import * as echarts from "echarts"



const props = defineProps({

trend:Array

})


const chartDom=ref(null)

let chart=null



function render(){


if(!chart)
return



let data =
props.trend || []



chart.setOption({

title:{
text:"近10天水质变化趋势",
left:"center"
},


tooltip:{},


xAxis:{


data:props.trend.map(

(item,index)=>{


    if(item.time){

        let date=new Date(item.time)

        return `${date.getMonth()+1}-${date.getDate()}`

    }


    return `第${index+1}天`

}

),


axisLabel:{


interval:1,


rotate:0


}


},



yAxis:{


type:"value"


},



series:[{


name:"水温",


type:"line",


smooth:true,


data:data.map(
x=>x.temperature
)


}]

})


}





onMounted(()=>{


chart =
echarts.init(
chartDom.value
)


render()


})



watch(
()=>props.trend,

()=>{

render()

},

{
deep:true
}

)



</script>



<template>

<div
ref="chartDom"
style="
width:100%;
height:300px
"
>


</div>

</template>