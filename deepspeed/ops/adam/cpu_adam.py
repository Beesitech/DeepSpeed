import math
import torch
import importlib

ds_opt_adam = None

class DeepSpeedCPUAdam(torch.optim.Optimizer):

    optimizer_id = 0

    def __init__(self,
                 model_params,
                 lr=1e-3,
                 bettas=(0.9,
                         0.999),
                 eps=1e-8,
                 weight_decay=0,
                 amsgrad=False):

        default_args = dict(lr=lr,
                            betas=bettas,
                            eps=eps,
                            weight_decay=weight_decay,
                            amsgrad=amsgrad)
        super(DeepSpeedCPUAdam, self).__init__(model_params, default_args)
        self.opt_id = DeepSpeedCPUAdam.optimizer_id
        DeepSpeedCPUAdam.optimizer_id = DeepSpeedCPUAdam.optimizer_id + 1

        global ds_opt_adam
        ds_opt_adam = importlib.import_module('deepspeed.ops.adam.cpu_adam_op')
        ds_opt_adam.create_adam(self.opt_id, lr, bettas[0], bettas[1], eps, weight_decay)

    def __setstate__(self, state):
        super(DeepSpeedCPUAdam, self).__setstate__(state)
        for group in self.param_groups:
            group.setdefault('amsgrad', False)

    @torch.no_grad()
    def step(self, closure=None, fp16_param_groups=None):
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        for i, group in enumerate(self.param_groups):
            for gid, p in enumerate(group['params']):

                if p.grad is None:
                    continue

                grad = p.grad
                state = self.state[p]
                # State initialization
                if len(state) == 0:
                    state['step'] = 0
                    # gradient momentums
                    state['exp_avg'] = torch.zeros_like(p, device='cpu')
                    # gradient variances
                    state['exp_avg_sq'] = torch.zeros_like(p, device='cpu')

                exp_avg, exp_avg_sq = state['exp_avg'], state['exp_avg_sq']
                state['step'] += 1

                if fp16_param_groups is not None:
                    p_fp16 = fp16_param_groups[i][gid]
                    ds_opt_adam.adam_update_copy(self.opt_id,
                                                 p,
                                                 grad,
                                                 exp_avg,
                                                 exp_avg_sq,
                                                 p_fp16)
                else:
                    ds_opt_adam.adam_update(self.opt_id, p, grad, exp_avg, exp_avg_sq)
        return loss
