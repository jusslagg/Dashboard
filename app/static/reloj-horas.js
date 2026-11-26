function dibujarRelojHoras(canvas, valor, gaugeTextColor){
    const dpr=devicePixelRatio||1,w=canvas.clientWidth||650,h=290;
    canvas.style.height=h+"px";
    canvas.width=w*dpr;canvas.height=h*dpr;
    const c=canvas.getContext('2d');c.scale(dpr,dpr);
    const x=w/2,y=235,r=Math.min(w*.4,195);
    const colors=['#ef4444','#f97316','#f59e0b','#84cc16'],sector=Math.PI/colors.length,gap=.018;
    c.lineWidth=58;
    colors.forEach((color,i)=>{
        c.beginPath();c.strokeStyle=color;
        c.arc(x,y,r,Math.PI+i*sector+(i?gap:0),Math.PI+(i+1)*sector-(i<colors.length-1?gap:0));
        c.stroke();
    });
    const recorrido=Math.min(Math.max(valor*.75,0),1),a=Math.PI+recorrido*Math.PI;
    const dx=Math.cos(a),dy=Math.sin(a),px=-dy,py=dx;
    c.beginPath();c.fillStyle=gaugeTextColor;
    c.moveTo(x+px*9,y+py*9);
    c.lineTo(x+dx*(r-7),y+dy*(r-7));
    c.lineTo(x-px*9,y-py*9);
    c.closePath();c.fill();
    c.beginPath();c.arc(x,y,12,0,Math.PI*2);c.fill();
    c.font='12px Montserrat';c.textAlign='center';
    c.fillText('0%',x-r,y+35);
    c.fillText('100%',x+Math.cos(Math.PI*1.75)*r,y+Math.sin(Math.PI*1.75)*r-13);
    c.fillText('133,33%',x+r,y+35);
}
