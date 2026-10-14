export class VisualState {
  actual='idle'; demo=null;
  setActual(state){this.actual=state;if(state!=='idle')this.demo=null;}
  setDemo(state){if(this.actual!=='idle')return false;this.demo=state;return true;}
  exitDemo(){this.demo=null;}
  get state(){return this.demo??this.actual;}
}
