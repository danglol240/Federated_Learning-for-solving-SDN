"""FedNova (Wang et al., 2020) - khong co san trong flwr nen tu cai dat bang
cach ke thua FedAvg va ghi de aggregate_fit.

Y tuong: moi client i tra ve trong so sau huan luyen local x_i, so buoc da
chay tau_i (client.py tra qua metrics["tau"]) va so mau n_i. FedNova chuan
hoa "huong di chuyen" cua tung client theo so buoc cua no truoc khi gop,
de client chay nhieu buoc hon khong lan at cac client chay it buoc hon
(van de "objective inconsistency" cua FedAvg voi local step khong deu -
dung xay ra khi cac vung SDN co luong du lieu/tai nguyen khac nhau).

Cong thuc (rut gon tu paper, global learning rate = 1):
    d_i        = (x_global - x_i) / tau_i          # gradient chuan hoa cua client i
    p_i        = n_i / sum_j(n_j)                  # trong so theo so mau
    tau_eff    = sum_i p_i * tau_i                  # so buoc hieu dung
    x_global'  = x_global - tau_eff * sum_i p_i * d_i
"""
from flwr.common import FitRes, Parameters, Scalar, ndarrays_to_parameters, parameters_to_ndarrays
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy import FedAvg


class FedNova(FedAvg):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._round_params = None

    def configure_fit(self, server_round, parameters, client_manager):
        self._round_params = parameters
        return super().configure_fit(server_round, parameters, client_manager)

    def aggregate_fit(
        self,
        server_round: int,
        results: list[tuple[ClientProxy, FitRes]],
        failures,
    ) -> tuple[Parameters | None, dict[str, Scalar]]:
        if not results:
            return None, {}
        if not self.accept_failures and failures:
            return None, {}

        global_ndarrays = parameters_to_ndarrays(self._round_params)
        total_examples = sum(fit_res.num_examples for _, fit_res in results)

        weighted_layers = None
        tau_eff = 0.0

        for _, fit_res in results:
            local_ndarrays = parameters_to_ndarrays(fit_res.parameters)
            tau_i = max(int(fit_res.metrics.get("tau", 1)), 1)
            p_i = fit_res.num_examples / total_examples

            d_i = [(g - l) / tau_i for g, l in zip(global_ndarrays, local_ndarrays)]

            if weighted_layers is None:
                weighted_layers = [p_i * layer for layer in d_i]
            else:
                weighted_layers = [acc + p_i * layer for acc, layer in zip(weighted_layers, d_i)]

            tau_eff += p_i * tau_i

        new_global = [g - tau_eff * layer for g, layer in zip(global_ndarrays, weighted_layers)]
        parameters_aggregated = ndarrays_to_parameters(new_global)

        metrics_aggregated = {}
        if self.fit_metrics_aggregation_fn:
            fit_metrics = [(res.num_examples, res.metrics) for _, res in results]
            metrics_aggregated = self.fit_metrics_aggregation_fn(fit_metrics)

        return parameters_aggregated, metrics_aggregated
