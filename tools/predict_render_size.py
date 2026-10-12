"""Mathematical prediction for fixed aspect-preserving scale trials, not GPU measurement."""
import argparse
from fractions import Fraction
import json
from math import ceil


def predict(base, target, multiplier):
    if len(base)!=2 or len(target)!=2 or any(type(x)!=int or not 1<=x<=65535 for x in [*base,*target]):
        raise ValueError('Unsupported dimensions')
    if type(multiplier)!=int or not -16<=multiplier<=16:
        raise ValueError('Unsupported multiplier')
    if multiplier==0:
        return list(base)
    width,height=[x*abs(multiplier) for x in target]
    if height*base[0]//base[1]<=width:
        width=height*base[0]//base[1]
    else:
        height=width*base[1]//base[0]
    factors=[Fraction(width,base[0]),Fraction(height,base[1])]
    if multiplier>0:factors=[ceil(x) for x in factors]
    return [max(size,int(size*factor)) for size,factor in zip(base,factors)]


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=int,nargs=2,default=[640,480])
    p.add_argument('--target',type=int,nargs=2,default=[1920,1080]);p.add_argument('--multiplier',type=int,default=-1)
    a=p.parse_args()
    print(json.dumps(dict(base=a.base,target_box=a.target,predicted_render=predict(a.base,a.target,a.multiplier),
                         measured=False,gpu_limits_checked=False,game_started=False)))
