from __future__ import division

import torch

from ignite.metrics.precision import _BasePrecisionRecall
from ignite._utils import to_onehot


class Recall(_BasePrecisionRecall):
    """
    Calculates recall for binary and multiclass data

    - `update` must receive output of the form `(y_pred, y)`.
    - `y_pred` must be in the following shape (batch_size, num_categories, ...) or (batch_size, ...)
    - `y` must be in the following shape (batch_size, ...)

    In binary and multilabel cases, the elements of `y` and `y_pred` should have 0 or 1 values. Thresholding of
    predictions can be done as below:

    .. code-block:: python

        def thresholded_output_transform(output):
            y_pred, y = output
            y_pred = torch.round(y_pred)
            return y_pred, y

        binary_accuracy = Recall(output_transform=thresholded_output_transform)

    In multilabel cases, average parameter should be True. If the user is trying to metrics to calculate F1 for
    example, average paramter should be False. This can be done as shown below:

    .. warning::

        If average is False, current implementation stores all input data (output and target) in as tensors before
        computing a metric. This can potentially lead to a memory error if the input data is larger than available RAM.

    .. code-block:: python

        precision = Precision(average=False, is_multilabel=True)
        recall = Recall(average=False, is_multilabel=True)
        F1 = precision * recall * 2 / (precision + recall + 1e-20)
        F1 = MetricsLambda(lambda t: torch.mean(t).item(), F1)

    Args:
        average (bool, optional): if True, precision is computed as the unweighted average (across all classes
            in multiclass case), otherwise, returns a tensor with the precision (for each class in multiclass case).
        is_multilabel (bool, optional) flag to use in multilabel case. By default, value is False. If True, average
            parameter should be True and the average is computed across samples, instead of classes.
    """

    def update(self, output):
        y_pred, y = self._check_shape(output)
        self._check_type((y_pred, y))

        if self._type == "binary":
            y_pred = y_pred.view(-1)
            y = y.view(-1)
        elif self._type == "multiclass":
            num_classes = y_pred.size(1)
            y = to_onehot(y.view(-1), num_classes=num_classes)
            indices = torch.max(y_pred, dim=1)[1].view(-1)
            y_pred = to_onehot(indices, num_classes=num_classes)
        elif self._type == "multilabel":
            # if y, y_pred shape is (N, C, ...) -> (C, N x ...)
            num_classes = y_pred.size(1)
            y_pred = torch.transpose(y_pred, 1, 0).reshape(num_classes, -1)
            y = torch.transpose(y, 1, 0).reshape(num_classes, -1)

        y = y.type_as(y_pred)
        correct = y * y_pred
        actual_positives = y.sum(dim=0).type(torch.DoubleTensor)  # Convert from int cuda/cpu to double cpu

        if correct.sum() == 0:
            true_positives = torch.zeros_like(actual_positives)
        else:
            true_positives = correct.sum(dim=0)

        # Convert from int cuda/cpu to double cpu
        # We need double precision for the division true_positives / actual_positives
        true_positives = true_positives.type(torch.DoubleTensor)

        if self._type == "multilabel":
            self._true_positives = torch.cat([self._true_positives, true_positives], dim=0)
            self._positives = torch.cat([self._positives, actual_positives], dim=0)
        else:
            self._true_positives += true_positives
            self._positives += actual_positives
